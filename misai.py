import re
import collections


Token = collections.namedtuple('Token', ['type', 'value', 'pos'])


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


class BinOp(Node):
    def parse(self, lexer):
        pass

    def render(self, context):
        pass


class RawNode(Node):
    def __init__(self, text):
        self.text = text

    def render(self, context):
        return self.text


class BlockNode(Node):
    def __init__(self):
        self.children = []

    def parse(self, lexer):
        while True:
            token = lexer.next()
            if token.type == 'eof':
                break
            elif token.type == 'raw':
                self.children.append(RawNode(token.value))
            elif token.type == 'ldelim':
                if lexer.lookup().type == 'keyword':
                    if token.value not in self.params['keywords']:
                        raise TemplateSyntaxError(
                            'unknown keyword: {}'.format(token.value),
                            source=lexer.source, pos=token.pos)
                    kw_class = self.context['keywords'][token.value]
                    self.children.append(kw_class.parse(lexer))
                else:
                    self.children.append(ExpressionNode().parse(lexer))
            else:
                raise TemplateSyntaxError(
                    'unexpected token: {}'.format(token.type),
                    source=lexer.source, pos=token.pos)
        return self

    def render(self, context):
        return ''.join([c.render(context) for c in self.children])


class ExpressionNode(Node):
    def __init__(self, simple=False):
        self.simple = simple

    def parse_or(self, lexer):
        pass

    def parse_and(self, lexer):
        pass

    def parse_comp(self, lexer):
        pass

    def parse_attr(self, lexer):
        pass

    def parse_atom(self, lexer):
        pass

    def parse_pipe(self, lexer):
        pass

    def parse_params(self, lexer):
        pass

    def parse(self, lexer):
        if self.simple:
            pass

        if lexer.lookup().type == 'id':
            node = IdNode(lexer.next().value)
            lexer.consume('rdelim')
            return node
        return self


class IdNode(Node):
    def __init__(self, name):
        self.name = name

    def render(self, context):
        return context.resolve(self.name)


class IfNode(Node):
    def parse(self, lexer):
        pass

    def render(self, lexer):
        pass


class Document(BlockNode):
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
    def __init__(self, source):
        self.source = source
        self.root = Document()
        self.root.parse(Lexer(self.source))

    def render(self, **context):
        return self.root.render(Context(context))


def render(source, context):
    return Template(source).render(**context)
