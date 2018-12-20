import ast
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


def attrgetter(obj, key):
    try:
        return obj[key]
    except (TypeError, LookupError, AttributeError):
        pass
    try:
        return getattr(obj, key)
    except AttributeError:
        pass


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

    def consume(self, token_type, token_value=None):
        token = self.next()
        if token.type != token_type:
            raise TemplateSyntaxError(
                'expected {}, got {}'.format(token_type, token.type),
                source=self.source,
                pos=token.pos)
        if token_value and token.value != token_value:
            raise TemplateSyntaxError(
                'expected {}, got {}'.format(token_value, token.value),
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
                (c(r'\b(if|else|elif|for|in|end|set)\b'), 'keyword'),

                (c(r':'), 'colon'),
                (c(r'\.'), 'dot'),
                (c(r','), 'comma'),
                (c(r'\|'), 'pipe'),
                (c(r'\('), 'lround'),
                (c(r'\)'), 'rround'),
                (c(r'\['), 'lsquare'),
                (c(r'\]'), 'rsquare'),
                (c(r'==|!=|<=|>=|<|>'), 'comp'),
                (c(r'='), 'assign'),
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
                lexer, until=['elif', 'else', 'end'])
            self.blocks.append([condition, body])
            token = lexer.next()
            if token.value == 'elif':
                condition = ExpressionNode('conditional').parse(lexer)
                lexer.consume('rdelim')
                continue
            elif token.value == 'else':
                lexer.consume('rdelim')
                body = NodeList().parse(lexer, until=['end'])
                self.blocks.append([None, body])
                lexer.consume('keyword')
                lexer.consume('rdelim')
            elif token.value == 'end':
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


class ForNode(Node):
    def __init__(self):
        self.target = None
        self.iter = None
        self.body = None

    def parse(self, lexer):
        self.target = lexer.consume('id').value
        lexer.consume('keyword', 'in')
        self.iter = ExpressionNode().parse(lexer)
        lexer.consume('rdelim')
        self.body = NodeList().parse(lexer, until=['end'])
        lexer.next()
        lexer.consume('rdelim')
        return self

    def render(self, context):
        result = []
        for item in self.iter.eval(context):
            subctx = Context({self.target: item}, context)
            result.append(self.body.render(subctx))
        return ''.join([str(r) for r in result])


class AssignNode(Node):
    def parse(self, lexer):
        self.varname = lexer.consume('id').value
        lexer.consume('assign')
        self.value = ExpressionNode().parse(lexer)
        lexer.consume('rdelim')
        return self

    def render(self, context):
        context.values[self.varname] = self.value.eval(context)
        return ''


class Document(NodeList):
    pass


class Context:
    def __init__(self, values, loader=None):
        self.scopes = [values]
        self.loader = loader

    def __setitem__(self, key, value):
        self.scopes[-1][key] = value

    def __getitem__(self, key):
        for i in range(len(self.scopes) - 1, -1, -1):
            if key in self.scopes[i]:
                return self.scopes[i][key]
        raise IndexError

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.scopes.pop()

    def __call__(self, values):
        self.scopes.append(values)


class IncludeNode(Node):
    def parse(self, lexer):
        self.path = lexer.consume('str').value
        lexer.consume('rdelim')

    def render(self, context):
        pass


class Compiler:
    def __init__(self, lexer, filename='<string>'):
        self.lexer = lexer
        self.filename = filename
        self.funcname = 'root'
        # todo: getattr
        self.getattr = 'attrgetter'
        self.context = 'context'
        self.tostr = 'tostr'
        self.filters = 'filters'
        self.keyword_handlers = {
            'set': self.assign,
            'if': self.if_}
        self.comp_map = {
            '==': ast.Eq,
            '!=': ast.NotEq,
            '<=': ast.LtE,
            '>=': ast.GtE,
            '<': ast.Lt,
            '>': ast.Gt,}

    def assign(self):
        var = self.lexer.consume('id').value
        self.lexer.consume('assign')
        node = ast.Assign(
            [ast.Subscript(ast.Name('context', ast.Load()),
             ast.Index(ast.Str(var)),
             ast.Store())],
            self.expr())
        self.lexer.consume('rdelim')
        return node

    def loop(self):
        pass

    def if_(self):
        cond = self.expr()
        root = node = ast.If(cond)
        self.lexer.consume('rdelim')
        while True:
            node.body = self.nodelist(until=['elif', 'else', 'end'])
            next = self.lexer.next()
            if next.value == 'elif':
                orelse = ast.If(self.expr())
                node.orelse = [orelse]
                node = orelse
                self.lexer.consume('rdelim')
                continue
            elif next.value == 'else':
                self.lexer.consume('rdelim')
                node.orelse = self.nodelist(until='end')
                self.lexer.consume('keyword', 'end')
                self.lexer.consume('rdelim')
            elif next.value == 'end':
                node.orelse = []
                self.lexer.consume('rdelim')
            break
        return root

    def atom(self):
        if self.lexer.lookup().type == 'str':
            return ast.Str(self.lexer.next().value)
        elif self.lexer.lookup().type in {'int', 'float'}:
            return ast.Num(self.lexer.next().value)
        else:
            raise RuntimeError('expected atom')

    def attr(self):
        if self.lexer.lookup().type == 'id':
            node = ast.Subscript(
                ast.Name(self.context, ast.Load()),
                ast.Index(ast.Str(self.lexer.next().value)),
                ast.Load())
            while self.lexer.lookup().type in {'dot', 'lsquare'}:
                x = self.lexer.next()
                if x.type == 'dot':
                    token = self.lexer.consume('id')
                    node = ast.Call(
                        ast.Name(self.getattr, ast.Load()),
                        [node, ast.Str(token.value)], [])
                elif x.type == 'lsquare':
                    node = ast.Call(
                        ast.Name(self.getattr, ast.Load()),
                        [node, self.attr()], [])
                    self.lexer.consume('rsquare')
            return node
        return self.atom()

    def params(self):
        p = []
        if self.lexer.lookup().type == 'colon':
            self.lexer.next()
            p.append(self.attr())
            while self.lexer.lookup().type == 'comma':
                self.lexer.next()
                p.append(self.attr())
        return p

    def pipe(self):
        node = self.attr()
        while self.lexer.lookup().type == 'pipe':
            self.lexer.next()
            filter_name = self.lexer.consume('id').value
            params = self.params()
            node = ast.Call(
                ast.Subscript(
                    ast.Name(self.filters, ast.Load()),
                    ast.Index(ast.Str(filter_name)),
                    ast.Load()),
                args=[node] + params,
                keywords=[])
        return node

    def comp(self):
        node = self.pipe()
        # TODO: check properly
        while self.lexer.lookup().type == 'comp':
            op = self.lexer.consume('comp').value
            node = ast.Compare(node, [self.comp_map[op]()], [self.pipe()])
        return node

    def and_(self):
        node = self.comp()
        # TODO: check properly
        while self.lexer.lookup().value == 'and':
            self.lexer.consume('logic')
            node = ast.BoolOp(ast.And(), [node, self.and_()])
        return node

    def or_(self):
        node = self.and_()
        # TODO: check properly
        while self.lexer.lookup().value == 'or':
            self.lexer.consume('logic')
            node = ast.BoolOp(ast.Or(), [node, self.and_()])
        return node

    def expr(self):
        return self.or_()

    def nodelist(self, until=None):
        children = []
        while True:
            token = self.lexer.next()
            if token.type == 'eof':
                break
            elif token.type == 'raw':
                children.append(ast.Expr(ast.Yield(ast.Str(token.value))))
            elif token.type == 'ldelim':
                if self.lexer.lookup().type == 'keyword':
                    if self.lexer.lookup().value not in self.keyword_handlers:
                        if until and self.lexer.lookup().value in until:
                            return children
                        raise TemplateSyntaxError(
                            'unknown keyword: {}'.format(token.value),
                            source=self.lexer.source, pos=token.pos)
                    token = self.lexer.next()
                    children.append(self.keyword_handlers[token.value]())
                else:
                    escaped = ast.Call(
                        ast.Name(self.tostr, ast.Load()), [self.expr()], [])
                    children.append(ast.Expr(ast.Yield(escaped)))
                    self.lexer.consume('rdelim')
            else:
                raise TemplateSyntaxError(
                    'unexpected token: {}'.format(token.type),
                    source=self.lexer.source, pos=token.pos)
        return children

    def compile(self, raw=False):
        funcname = 'root'

        tmpl = self.nodelist()
        tmpl_wrapper = ast.FunctionDef(
            self.funcname,
            ast.arguments(
                args=[
                    ast.arg(self.context, annotation=None),
                    ast.arg(self.tostr, annotation=None),
                    ast.arg(self.filters, annotation=None),
                    ast.arg(self.getattr, annotation=None)],
                kwonlyargs=[], kw_defaults=[], defaults=[],
                vararg=None, kwarg=None),
            tmpl,
            decorator_list=[])
        tmpl_module = ast.Module([tmpl_wrapper])

        ast.fix_missing_locations(tmpl_module)

        if raw:
            return tmpl_module

        code = compile(tmpl_module, self.filename, mode='exec', optimize=2)
        code_env = {}
        exec(code, code_env)
        return code_env[self.funcname]


class Template:
    keywords = {
        'if': IfNode,
        'for': ForNode,
        'set': AssignNode,
        'use': IncludeNode,
    }

    def __init__(self, source, loader=None):
        self.loader = loader
        self.source = source
        self.code = Compiler(Lexer(self.source)).compile()

    @property
    def compiled(self):
        import astor
        code_ast = Compiler(Lexer(self.source)).compile(raw=True)
        return astor.to_source(code_ast)

    def render(self, **context):
        return ''.join(self.code(
            Context(context, loader=self.loader),
            lambda x: str(x),
            filter,
            attrgetter))


class Loader:
    def __init__(self):
        self.cache = {}

    def get(self, path):
        source = self.get_contents(path)
        return Template(source, loader=self)

    def get_contents(self, path):
        with open(path) as f:
            return f.read()


def render(source, context=None):
    context = context or {}
    print('>>', Template(source).compiled)
    return Template(source).render(**context)
