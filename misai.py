import ast
import re
import operator
import collections


Token = collections.namedtuple('Token', ['type', 'value', 'pos'])


class astutils:
    @staticmethod
    def Call(func, *args):
        return ast.Call(
            func=ast.Name(id=func, ctx=ast.Load()),
            args=list(args), keywords=[])


class Filters(dict):
    def __call__(self, func=None, **params):
        if callable(func):
            self[func.__name__] = func
        else:
            def wrapper(func):
                self[params['name']] = func
            return wrapper


filter = Filters()


def attr(obj, key):
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
        return self


class Compiler:
    def __init__(self, lexer, filename='<string>'):
        self.lexer = lexer
        self.filename = filename
        self.funcname = 'root'
        # todo: getattr
        self.param_getattr = 'attrgetter'
        self.param_context = 'context'
        self.param_tostr = 'tostr'
        self.param_filters = 'filters'
        self.varcount = -1
        self.keyword_handlers = {
            'set': self.assign,
            'if': self.cond,
            'for': self.loop}
        self.comp_map = {
            '==': ast.Eq,
            '!=': ast.NotEq,
            '<=': ast.LtE,
            '>=': ast.GtE,
            '<': ast.Lt,
            '>': ast.Gt,}

    def _unique_name(self):
        self.varcount += 1
        return 'var' + str(self.varcount)

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
        target = self.lexer.consume('id').value
        self.lexer.consume('keyword', 'in')
        iter = self.expr()
        self.lexer.consume('rdelim')
        body = self.nodelist(until=['end'])
        self.lexer.consume('keyword', 'end')
        self.lexer.consume('rdelim')

        varname = self._unique_name()
        stmt_ctx_call = astutils.Call(
            self.param_context,
            ast.Dict([ast.Str(target)], [ast.Name(varname, ast.Load())]))
        stmt_with = ast.With([ast.withitem(stmt_ctx_call, None)], body)
        return ast.For(ast.Name(varname, ast.Store()), iter, [stmt_with], [])

    def cond(self):
        cond = self.expr()
        root = node = ast.If(test=cond, body=[], orelse=[])
        self.lexer.consume('rdelim')
        while True:
            node.body = self.nodelist(until=['elif', 'else', 'end'])
            next = self.lexer.next()
            if next.value == 'elif':
                orelse = ast.If(test=self.expr(), body=[], orelse=[])
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
                ast.Name(self.param_context, ast.Load()),
                ast.Index(ast.Str(self.lexer.next().value)),
                ast.Load())
            while self.lexer.lookup().type in {'dot', 'lsquare'}:
                x = self.lexer.next()
                if x.type == 'dot':
                    token = self.lexer.consume('id')
                    node = astutils.Call(self.param_getattr, node, ast.Str(token.value))
                elif x.type == 'lsquare':
                    node = astutils.Call(self.param_getattr, node, self.attr())
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
                func=ast.Subscript(
                    ast.Name(self.param_filters, ast.Load()),
                    ast.Index(ast.Str(filter_name)),
                    ast.Load()),
                args=[node] + params, keywords=[])
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
                    escaped = astutils.Call(self.param_tostr, self.expr())
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
            name=self.funcname,
            args=ast.arguments(
                args=[
                    ast.arg(arg=self.param_context, annotation=None),
                    ast.arg(arg=self.param_tostr, annotation=None),
                    ast.arg(arg=self.param_filters, annotation=None),
                    ast.arg(arg=self.param_getattr, annotation=None)],
                kwonlyargs=[], kw_defaults=[], defaults=[],
                vararg=None, kwarg=None),
            body=tmpl,
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
    def __init__(self, content, loader=None):
        self.loader = loader
        self.content = content
        self.func = Compiler(Lexer(self.content)).compile()

    @property
    def code(self):
        import astor
        code_ast = Compiler(Lexer(self.source)).compile(raw=True)
        return astor.to_source(code_ast)

    def render(self, **context):
        return ''.join(self.func(
            Context(context, loader=self.loader),
            lambda x: str(x),
            filter,
            attr))


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
    return Template(source).render(**context)
