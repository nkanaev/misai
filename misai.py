import ast
import collections
import os
import re
import sys


Token = collections.namedtuple('Token', ['type', 'value', 'pos'])


class noescapestr(str):
    pass


class astutils:
    @staticmethod
    def Call(func, *args):
        return ast.Call(
            func=ast.Name(id=func, ctx=ast.Load()),
            args=list(args), keywords=[])

    @staticmethod
    def With(expr, body):
        if sys.version_info[0] == 2:
            return ast.With(context_expr=expr, optional_vars=None, body=body)
        return ast.With(items=[ast.withitem(context_expr=expr, optional_vars=None)], body=body)

    @staticmethod
    def FunctionDef(name, args, body):
        if sys.version_info[0] == 2:
            args = [ast.Name(id=arg, ctx=ast.Param()) for arg in args]
        else:
            args = [ast.arg(arg=arg, annotation=None) for arg in args]

        if sys.version_info[:3] >= (3, 8, 0):
            args = ast.arguments(
                args=args,
                kwonlyargs=[], kw_defaults=[], defaults=[],
                vararg=None, kwarg=None, posonlyargs=[])
        else:
            args = ast.arguments(
                args=args,
                kwonlyargs=[], kw_defaults=[], defaults=[],
                vararg=None, kwarg=None)

        return ast.FunctionDef(
            name=name,
            args=args,
            body=body,
            decorator_list=[])


class Filters(dict):
    def __call__(self, func):
        if callable(func):
            self[func.__name__] = func
            return func
        else:
            def wrapper(callable):
                self[func] = callable
            return wrapper


filter = Filters()


@filter
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


@filter
def htmlescape(input):
    if isinstance(input, noescapestr):
        return input
    return str(input)\
        .replace('&', '&amp;')\
        .replace('<', '&lt;')\
        .replace('>', '&gt;')\
        .replace('"', '&#34;')\
        .replace("'", '&#39;')


@filter
def noescape(input):
    return noescapestr(input)


@filter
def split(input, delim=None):
    return str(input).split(delim)


class TemplateSyntaxError(Exception):
    def __init__(self, msg, source, pos):
        self.msg = msg
        self.source = source
        self.pos = pos
        self.lineno = source[:pos].count('\n') + 1
        self.colno = pos - source.rfind('\n', 0, pos)
        super().__init__(
            '%s (at line %d, col %d)' % (self.msg, self.lineno, self.colno))


class RuntimeError(Exception):
    pass


class Lexer:
    def __init__(self, source, cleanlines=True):
        self.source = source
        self.cache = collections.deque()
        self.tokens = list(self.tokenize())
        if cleanlines:
            self.clean(self.tokens)
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

    def next_is(self, token_type, token_value=None):
        lookup = self.lookup()
        if token_value:
            return lookup.type == token_type and lookup.value == token_value
        return lookup.type == token_type

    def lookup(self, offset=0):
        return self.tokens[self.idx]

    def next(self):
        i, self.idx = self.idx, self.idx + 1
        if i >= len(self.tokens):
            return Token('eof', None, None)
        return self.tokens[i]

    def clean(self, tokens):
        il, ir = None, None
        for i in range(len(tokens)):
            if tokens[i].type == 'ldelim':
                il = i
            elif tokens[i].type == 'rdelim':
                ir = i

                if not il or tokens[il + 1].type != 'keyword':
                    il, ir = None, None
                    continue

                m_l = (il == 0) \
                    or (tokens[il - 1].type == 'raw'
                        and re.search('(^|\n|\r\n)[ \t]*$', tokens[il - 1].value))
                m_r = (ir == len(tokens) - 1) \
                    or (tokens[ir + 1].type == 'raw'
                        and re.search('^[ \t]*(\n|\r\n)', tokens[ir + 1].value))

                if m_l and m_r:
                    if il != 0:
                        oldtoken = tokens[il - 1]
                        newvalue = re.sub('[ \t]*$', '', oldtoken.value)
                        newtoken = Token('raw', newvalue, oldtoken.pos)
                        tokens[il - 1] = newtoken
                    if ir != len(tokens) - 1:
                        oldtoken = tokens[ir + 1]
                        newvalue = re.sub('^[ \t]*(\n|\r\n)', '', oldtoken.value)
                        newtoken = Token('raw', newvalue, oldtoken.pos)
                        tokens[ir + 1] = newtoken

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
                (c(r'#(\w+)'), 'keyword'),

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
    def __init__(self, values):
        self.scopes = [values]

    def __setitem__(self, key, value):
        self.scopes[-1][key] = value

    def __getitem__(self, key):
        for i in range(len(self.scopes) - 1, -1, -1):
            if key in self.scopes[i]:
                return self.scopes[i][key]
        raise IndexError(key)

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
        self.varcount = -1

        self.param_context = 'context'
        self.param_tostr = 'tostr'
        self.param_filters = 'filters'
        self.param_getattr = 'attr'
        self.param_loader = 'load'

        self.keyword_handlers = {
            'set': self.assign,
            'if': self.cond,
            'for': self.loop,
            'add': self.include}
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

    def include(self):
        path = self.lexer.consume('str').value
        keys, values = [], []
        while self.lexer.next_is('id'):
            keys.append(ast.Str(s=self.lexer.consume('id').value))
            self.lexer.consume('assign')
            values.append(self.expr())
        self.lexer.consume('rdelim')
        call = astutils.Call(
            self.param_loader, ast.Str(s=path), ast.Dict(keys=keys, values=values))
        return ast.Expr(ast.Yield(call))

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
        self.lexer.consume('colon')
        iter = self.expr()
        self.lexer.consume('rdelim')
        body = self.nodelist(until=['end'])
        self.lexer.consume('keyword', 'end')
        self.lexer.consume('rdelim')

        varname = self._unique_name()
        stmt_ctx_call = astutils.Call(
            self.param_context,
            ast.Dict(keys=[ast.Str(target)], values=[ast.Name(varname, ast.Load())]))
        stmt_with = astutils.With(stmt_ctx_call, body)
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
        if self.lexer.next_is('str'):
            return ast.Str(self.lexer.next().value)
        elif self.lexer.lookup().type in {'int', 'float'}:
            return ast.Num(self.lexer.next().value)
        elif self.lexer.next_is('lround'):
            self.lexer.next()
            node = self.expr()
            self.lexer.consume('rround')
            return node
        else:
            token = self.lexer.lookup()
            raise TemplateSyntaxError(
                'expected atom, got {}'.format(token.value),
                source=self.lexer.source, pos=token.pos)

    def attr(self):
        if self.lexer.next_is('id'):
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
        if self.lexer.next_is('colon'):
            self.lexer.next()
            p.append(self.attr())
            while self.lexer.next_is('comma'):
                self.lexer.next()
                p.append(self.attr())
        return p

    def pipe(self):
        node = self.attr()
        while self.lexer.next_is('pipe'):
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
        while self.lexer.next_is('comp'):
            op = self.lexer.consume('comp').value
            node = ast.Compare(node, [self.comp_map[op]()], [self.pipe()])
        return node

    def and_(self):
        node = self.comp()
        while self.lexer.next_is('logic', 'and'):
            self.lexer.consume('logic')
            node = ast.BoolOp(ast.And(), [node, self.and_()])
        return node

    def or_(self):
        node = self.and_()
        while self.lexer.next_is('logic', 'or'):
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
                if self.lexer.next_is('keyword'):
                    next = self.lexer.lookup()
                    if next.value not in self.keyword_handlers:
                        if until and next.value in until:
                            return children
                        raise TemplateSyntaxError(
                            'unknown keyword: {}'.format(next.value),
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
        tmpl = self.nodelist()
        tmpl_wrapper = astutils.FunctionDef(
            name=self.funcname,
            args=[
                self.param_context,
                self.param_tostr,
                self.param_filters,
                self.param_getattr,
                self.param_loader,
            ],
            body=tmpl)

        if sys.version_info[:3] >= (3, 8, 0):
            tmpl_module = ast.Module([tmpl_wrapper], type_ignores=[])
        else:
            tmpl_module = ast.Module([tmpl_wrapper])

        ast.fix_missing_locations(tmpl_module)

        if raw:
            return tmpl_module

        code = compile(tmpl_module, self.filename, mode='exec')
        code_env = {}
        exec(code, code_env)
        return code_env[self.funcname]


class Template:
    def __init__(self, content, loader=None, filepath=None, **options):
        self.loader = loader
        self.content = content
        self.formatter = htmlescape if options.get('autoescape', True) else str
        self.filepath = filepath
        self.locals = options.get('locals', {})
        self.func = Compiler(Lexer(self.content, options.get('cleanlines', True))).compile()
        self.load = lambda path, params: self.loader.get(path, self).render(**params)

    def render(self, **params):
        if self.locals:
            ctx = Context(self.locals)
            ctx(params)
        else:
            ctx = Context(params)
        return ''.join(self.func(ctx, self.formatter, filter, attr, self.load))


class Loader:
    def __init__(self, basedir, **params):
        self.basedir = basedir
        self.params = params

    def get(self, filepath, template=None):
        if filepath.startswith('./'):
            filepath = os.path.join(os.path.dirname(template.filepath), filepath[2:])
        fullpath = os.path.join(self.basedir, filepath)
        # TODO: check if fullpath is in basedir
        with open(fullpath) as f:
            x = f.read()
            return Template(x, loader=self, filepath=filepath, **self.params)


def render(source, context=None):
    context = context or {}
    return Template(source).render(**context)
