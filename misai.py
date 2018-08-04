import re
import operator
import collections


Token = collections.namedtuple('Token', ['type', 'value', 'pos'])


class Filters(dict):

    def __call__(self, func=None, **params):
        if callable(func):
            self[func.__name__] = func
        else:
            def wrapper(func):
                self[params['name']] = func
            return wrapper


filter = Filters()


@filter
def capitalize(string):
    return string.capitalize()


@filter
def strip(string):
    return string.strip()


class TemplateSyntaxError(Exception):
    def __init__(self, msg, source=None, pos=None):
        self.msg = msg
        self.source = source
        self.pos = pos


class Lexer:
    def __init__(self, source):
        self.source = source
        self.cache = collections.deque()
        self.tokens = list(self.tokenize())
        self.idx = 0

    def consume(self, token_type):
        token = self.next()
        if token.type != token_type:
            raise TemplateSyntaxError(
                'expected {}, got {}'.format(token_type, token.type),
                source=self.source,
                pos=token.pos)
        return token

    def lookup(self, offset=0):
        return self.tokens[self.idx]

    def next(self):
        i, self.idx = self.idx, self.idx + 1
        if i >= len(self.tokens):
            return Token('eof', None, None)
        return self.tokens[i]

    def tokenize(self):
        c = re.compile
        ldelim = '{{'
        rdelim = '}}'
        esc_ldelim = re.escape(ldelim)
        esc_rdelim = re.escape(rdelim)
        rules = {
            'root': [
                (c(r'%s#.+?#%s' % (esc_ldelim, esc_rdelim), re.S), 'comment'),
                (c(r'(.*?)' + esc_ldelim, re.S), 'ldelim'),
                (c(r'(.+)', re.S), 'raw'),
            ],
            'block': [
                (c(esc_rdelim), 'rdelim'),
                (c(r'\s+'), 'ws'),

                # keyword
                (c(r'#[a-z]+'), 'keyword'),

                (c(r':'), 'colon'),
                (c(r'\.'), 'dot'),
                (c(r','), 'comma'),
                (c(r'\|'), 'pipe'),
                (c(r'\('), 'lround'),
                (c(r'\)'), 'rround'),
                (c(r'\['), 'lsquare'),
                (c(r'\]'), 'rsquare'),
                (c(r'==|!=|<=|>=|<|>'), 'comp'),
                (c(r'\b(and|or)\b'), 'logic'),

                # literals
                (c(r'\d+\.\d+\b'), 'float'),
                (c(r'\d+\b'), 'int'),
                (c(r'"(([^"\\]|\\.)*)"'), 'str'),
                (c(r"'(([^'\\]|\\.)*)'"), 'str'),
                (c(r'\b(\w+)\b'), 'id'),
            ]
        }
        inside_delim = False
        pos = 0
        while pos < len(self.source):
            for regex, name in rules['block' if inside_delim else 'root']:
                m = regex.match(self.source, pos)
                if not m:
                    continue

                if pos == m.end() and name != 'ldelim':
                    # should not never happen
                    msg = '{} yielded empty string'.format(regex)
                    raise TemplateSyntaxError(msg)

                pos_prev, pos = pos, m.end()
                name = name or m.group()
                match = m.group(1) if m.groups() else m.group()

                if inside_delim:
                    if name == 'ws':
                        break

                    value = match
                    if name == 'rdelim':
                        inside_delim = False
                    elif name == 'int':
                        value = int(match)
                    elif name == 'float':
                        value = float(match)
                    elif name == 'str':
                        value = match\
                            .replace(r'\"', '"')\
                            .replace(r"\'", "'")

                    yield Token(name, value, pos_prev)

                    break
                else:
                    if name == 'comment':
                        break
                    elif name == 'ldelim':
                        if len(match) > 0:
                            yield Token('raw', match, pos)
                        yield Token('ldelim', ldelim, pos - len(ldelim))
                        inside_delim = True
                    else:
                        yield Token(name, match, pos)
                    break
            else:
                msg = 'unexpected char {}'.format(repr(self.source[pos]))
                raise TemplateSyntaxError(msg, pos=pos, source=self.source)


class Node:
    def parse(self, lexer):
        raise NotImplementedError

    def reunder(self, context):
        raise NotImplementedError


class RawNode(Node):
    def __init__(self, text):
        self.text = text

    def render(self, context):
        return self.text


class NodeList(Node):
    def __init__(self):
        self.children = []

    def parse(self, lexer, until=None):
        while True:
            token = lexer.next()
            if token.type == 'eof':
                break
            elif token.type == 'raw':
                self.children.append(RawNode(token.value))
            elif token.type == 'ldelim':
                if lexer.lookup().type == 'keyword':
                    if lexer.lookup().value not in Template.keywords:
                        if until and lexer.lookup().value in until:
                            return self
                        raise TemplateSyntaxError(
                            'unknown keyword: {}'.format(token.value),
                            source=lexer.source, pos=token.pos)
                    token = lexer.next()
                    kw_class = Template.keywords[token.value]
                    self.children.append(kw_class().parse(lexer))
                else:
                    self.children.append(ExpressionNode().parse(lexer))
                    lexer.consume('rdelim')
            else:
                raise TemplateSyntaxError(
                    'unexpected token: {}'.format(token.type),
                    source=lexer.source, pos=token.pos)
        return self

    def render(self, context):
        return ''.join([c.render(context) for c in self.children])


class AttrNode(Node):
    def __init__(self, data, value):
        self.data = data
        self.name = value

    def render(self, context):
        data = self.data.render(context)
        name = self.name.render(context)
        if hasattr(data, '__getitem__'):
            return data[name]
        return getattr(data, name)


class BinopNode(Node):

    ops = {
        '==': operator.eq,
        '!=': operator.ne,
        '<=': operator.le,
        '>=': operator.ge,
        '<': operator.lt,
        '>': operator.gt,
        'and': operator.and_,
        'or': operator.or_,
    }

    def __init__(self, op_value, left, right):
        self.op = self.ops[op_value]
        self.left = left
        self.right = right

    def render(self, context):
        return self.op(self.left.render(context), self.right.render(context))


class LiteralNode(Node):
    def __init__(self, val):
        self.val = val

    def render(self, context):
        return self.val


class PipeNode(Node):
    def __init__(self, node, func, params):
        self.node = node
        self.func = func
        self.params = params or []

    def render(self, context):
        if self.func not in filter:
            raise RuntimeError('unknown filter: {}'.format(self.func))
        callable = filter[self.func]
        first_param = self.node.render(context)
        params = [p.render(context) for p in self.params]
        return callable(first_param, *params)


class ExpressionNode(Node):

    def __init__(self, mode='simple'):
        self.mode = mode

    def parse_or(self, lexer, *params):
        node = self.parse_and(lexer)
        while lexer.lookup().value == 'or':
            token = lexer.consume('logic')
            node = BinopNode(token.value, node, self.parse_and(lexer))
        return node

    def parse_and(self, lexer):
        node = self.parse_comp(lexer)
        while lexer.lookup().value == 'and':
            token = lexer.consume('logic')
            node = BinopNode(token.value, node, self.parse_comp(lexer))
        return node

    def parse_comp(self, lexer):
        node = self.parse_attr(lexer)
        while lexer.lookup().type == 'comp':
            token = lexer.next()
            node = BinopNode(token.value, node, self.parse_attr(lexer))
        return node

    def parse_attr(self, lexer):
        if lexer.lookup().type == 'id':
            node = IdNode(lexer.next().value)
            while lexer.lookup().type in {'dot', 'lsquare'}:
                if lexer.lookup().type == 'dot':
                    lexer.next()
                    token = lexer.consume('id')
                    node = AttrNode(node, LiteralNode(token.value))
                elif lexer.lookup().type == 'lsquare':
                    lexer.next()
                    node = AttrNode(node, self.parse_attr(lexer))
                    lexer.consume('rsquare')
            return node
        return self.parse_atom(lexer)

    def parse_atom(self, lexer):
        if lexer.lookup().type in {'str', 'int', 'float'}:
            return LiteralNode(lexer.next().value)
        raise RuntimeError('expected atom')

    def parse_pipe(self, lexer):
        node = self.parse_attr(lexer)
        while lexer.lookup().type == 'pipe':
            lexer.consume('pipe')
            filter = lexer.consume('id')
            params = self.parse_params(lexer)
            node = PipeNode(node, filter.value, params)
        return node

    def parse_params(self, lexer):
        params = []
        if lexer.lookup().type == 'colon':
            lexer.consume('colon')
            params.append(self.parse_atom(lexer))
            while lexer.lookup().type == 'comma':
                lexer.consume('comma')
                params.append(self.parse_atom(lexer))
        return params

    def parse(self, lexer):
        if self.mode == 'simple':
            self.root = self.parse_pipe(lexer)
        elif self.mode == 'conditional':
            self.root = self.parse_or(lexer)
        return self

    def eval(self, context):
        return self.root.render(context)

    def render(self, context):
        result = self.eval(context)
        if result is None:
            return ''
        return str(result)


class IdNode(Node):
    def __init__(self, name):
        self.name = name

    def render(self, context):
        return context.resolve(self.name)


class IfNode(Node):
    def __init__(self):
        self.blocks = []

    def parse(self, lexer):
        condition = ExpressionNode('conditional').parse(lexer)
        lexer.consume('rdelim')
        while True:
            body = NodeList().parse(
                lexer, until=['#elseif', '#else', '#endif'])
            self.blocks.append([condition, body])
            token = lexer.next()
            if token.value == '#elseif':
                condition = ExpressionNode('conditional').parse(lexer)
                lexer.consume('rdelim')
                continue
            elif token.value == '#else':
                lexer.consume('rdelim')
                body = NodeList().parse(lexer, until=['#endif'])
                self.blocks.append([None, body])
                lexer.consume('keyword')
                lexer.consume('rdelim')
            elif token.value == '#endif':
                lexer.consume('rdelim')
            break
        return self

    def render(self, context):
        for condition, body in self.blocks:
            if condition is None:
                return body.render(context)
            elif condition.eval(context):
                return body.render(context)
        return ''


class Document(NodeList):
    pass


class Context:
    def __init__(self, values, parent=None):
        self.parent = parent
        self.values = values

    def resolve(self, varname):
        if varname in self.values:
            return self.values[varname]
        if self.parent:
            return self.parent.resolve(varname)
        raise RuntimeError('unresolved variable: {}'.format(varname))


class Template:
    keywords = {
        '#if': IfNode,
    }

    def __init__(self, source):
        self.source = source
        self.root = Document()
        self.root.parse(Lexer(self.source))

    def render(self, **context):
        return self.root.render(Context(context))


def render(source, context):
    return Template(source).render(**context)
