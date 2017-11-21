import re
import operator
import collections


Token = collections.namedtuple('Token', ['type', 'value', 'pos'])


class TemplateSyntaxError(Exception):
    pass

class RuntimeError(Exception):
    pass


def tokenize(template, ldelim='{{', rdelim='}}'):
    c = re.compile
    ldelim = re.escape(ldelim)
    rdelim = re.escape(rdelim)
    rules = {
        'root': [
            (c(r'%s#.+?#%s' % (ldelim, rdelim), re.S), 'comment'),
            (c(r'(.*?)' + ldelim, re.S), 'ldelim'),
            (c(r'(.+)', re.S), 'raw'),
        ],
        'block': [
            (c(rdelim), 'rdelim'),
            (c(r'\s+'), 'ws'),

            # keywords
            (c(r'#if'), '#if'),
            (c(r'#for'), '#for'),
            (c(r'#elseif'), '#elseif'),
            (c(r'#else'), '#else'),
            (c(r'#endif'), '#endif'),
            (c(r'#endfor'), '#endfor'),

            # one/two character tokens
            (c(r'\.'), 'dot'),
            (c(r'\['), 'lsquare'),
            (c(r'\]'), 'rsquare'),
            (c(r':'), 'colon'),
            (c(r'==|!=|<=|>=|<|>'), None),
            (c(r'\+|\-|\*|\/|\%'), None),

            # literals
            (c(r'\d+'), 'int'),
            (c(r'".+"'), 'str'),
            (c(r'\b\w+\b'), 'id'),
       ]
    }
    inside_delim = False
    pos = 0
    while pos < len(template):
        for regex, name in rules['block' if inside_delim else 'root']:
            m = regex.match(template, pos)
            if not m:
                continue

            if pos == m.end() and name != 'ldelim':
                # should not never happen
                msg = '{} yielded empty string'.format(regex)
                raise TemplateSyntaxError(msg)

            pos = m.end()

            name = name or m.group()

            if inside_delim and name == 'ws':
                break

            if inside_delim:
                yield Token(name, m.group(), pos)
                if name == 'rdelim':
                    inside_delim = False
                break
            else:
                if name != 'comment' and m.group(1):
                    yield Token('raw', m.group(1), pos)
                if name == 'ldelim':
                    yield Token('ldelim', ldelim, pos)
                    inside_delim = True
                break
        else:
            msg = 'unexpected char {} at {}'.format(repr(template[pos]), pos)
            raise TemplateSyntaxError(msg)
    yield Token('eof', None, pos)


class LookupIter:
    def __init__(self, iter):
        self.iter = iter
        self.cache = collections.deque()

    @property
    def lookup(self):
        if not self.cache:
            self.cache.append(next(self.iter))
        return self.cache[0]

    def expect(self, token_type, ignore=False):
        if self.lookup.type != token_type:
            raise TemplateSyntaxError(
                'expected {}, got {}'.format(token_type, self.lookup.type))
        if ignore:
            self.next()

    def next(self):
        x = self.cache.popleft() if self.cache else next(self.iter)
        return x


class Parser:
    def __init__(self, template):
        self.tokeniter = LookupIter(tokenize(template))

    def fail(self, msg):
        raise TemplateSyntaxError(msg)

    def parse_if(self):
        self.tokeniter.expect('#if', ignore=True)
        result = node = {'type': 'if'}
        while 1:
            node['test'] = self.parse_expr()
            self.tokeniter.expect('rdelim', ignore=True)
            node['body'] = self.parse(until=['#else', '#elseif', '#endif'])
            if self.tokeniter.lookup.type == '#elseif':
                self.tokeniter.next()
                subnode = {'type': 'if'}
                node['else'] = subnode
                node = subnode
                continue
            elif self.tokeniter.lookup.type == '#else':
                self.tokeniter.next()
                self.tokeniter.expect('rdelim', ignore=True)
                node['else'] = self.parse(until=['#endif'])
                self.tokeniter.next()
                self.tokeniter.expect('rdelim', ignore=True)
            elif self.tokeniter.lookup.type == '#endif':
                self.tokeniter.next()
                self.tokeniter.expect('rdelim', ignore=True)
            break
        return result

    def parse_for(self):
        self.tokeniter.expect('#for', ignore=True)
        result = {'type': 'for'}
        result['target'] = self.parse_id()
        self.tokeniter.expect('colon', ignore=True)
        result['iter'] = self.parse_expr()
        self.tokeniter.expect('rdelim', ignore=True)
        result['body'] = self.parse(until=['#endfor'])
        self.tokeniter.next()
        self.tokeniter.expect('rdelim', ignore=True)
        return result

    def parse_expr(self):
        return self.parse_eq()

    def parse_eq(self):
        left = self.parse_comparison()
        while self.tokeniter.lookup.type in {'==', '!='}:
            token = self.tokeniter.next()
            right = self.parse_comparison()
            left = {'type': 'binop', 'left': left, 'right': right, 'op': token.type}
        return left

    def parse_comparison(self):
        left = self.parse_add()
        while self.tokeniter.lookup.type in {'<', '>', '<=', '>='}:
            token = self.tokeniter.next()
            right = self.parse_add()
            left = {'type': 'binop', 'left': left, 'right': right, 'op': token.type}
        return left

    def parse_add(self):
        left = self.parse_mul()
        while self.tokeniter.lookup.type in {'+', '-'}:
            token = self.tokeniter.next()
            right = self.parse_mul()
            left = {'type': 'binop', 'left': left, 'right': right, 'op': token.type}
        return left

    def parse_mul(self):
        left = self.parse_unary()
        while self.tokeniter.lookup.type in {'*', '/', '%'}:
            token = self.tokeniter.next()
            right = self.parse_unary()
            left = {'type': 'binop', 'left': left, 'right': right, 'op': token.type}
        return left

    def parse_unary(self):
        if self.tokeniter.lookup.type in {'-', '!'}:
            self.tokeniter.next()
            return {'type': 'unary', 'value': self.parse_unary()}
        return self.parse_primary()

    def parse_primary(self):
        lookup = self.tokeniter.lookup
        if lookup.type == 'int':
            token = self.tokeniter.next()
            node = {'type': 'num', 'value': token.value}
        elif lookup.type == 'str':
            token = self.tokeniter.next()
            node = {'type': 'str', 'value': token.value}
        elif lookup.type == 'lparen':
            self.tokeniter.next()
            expr = self.parse_expr()
            self.tokeniter.expect('rparen', ignore=True)
            node = expr
        else:
            node = self.parse_id()

        # subscript
        while self.tokeniter.lookup.type in {'dot', 'lsquare'}:
            if self.tokeniter.lookup.type == 'dot':
                self.tokeniter.next()
                node = {'type': 'attr', 'value': node, 'attr': self.parse_id()}
            else:
                self.tokeniter.next()
                node = {'type': 'index', 'value': node, 'index': self.parse_expr()}
                self.tokeniter.expect('rsquare', ignore=True)

        return node

    def parse_id(self):
        self.tokeniter.expect('id')
        token = self.tokeniter.next()
        return {'type': 'id', 'value': token.value}

    def parse(self, until=None):
        nodes = []
        while True:
            token = self.tokeniter.next()
            if token.type == 'raw':
                nodes.append({'type': 'raw', 'value': token.value})
            elif token.type == 'ldelim':
                token = self.tokeniter.lookup
                if token.type == '#if':
                    nodes.append(self.parse_if())
                elif token.type == '#for':
                    nodes.append(self.parse_for())
                elif until and token.type in until:
                    break
                else:
                    nodes.append(self.parse_expr())
                    self.tokeniter.expect('rdelim', ignore=True)
            elif token.type == 'eof':
                break
            else:
                # should never happen
                raise Exception('unknown parser error')
        return nodes


class Interpreter:
    operators = {
        '+': operator.add,
        '-': operator.sub,
        '*': operator.mul,
        '/': operator.truediv,
        '%': operator.mod,
        '!=': operator.ne,
        '==': operator.eq,
        '>=': operator.le,
        '<=': operator.ge,
    }

    def __init__(self, ast, loader=None):
        self.ast = ast
        self.loader = None

    def visit_binop(self, node):
        left = self.visit(node['left'])
        right = self.visit(node['right'])
        return self.operators[node['op']](left, right)

    def visit_num(self, node):
        return int(node['value'])

    def visit_id(self, node):
        return self.context[node['value']]

    def visit_attr(self, node):
        value = self.visit(node['value'])
        while True:
            value = getattr(
                value,
                node['attr']['value'],
                value[node['attr']['value']])
            if node['attr']['type'] == 'attr':
                node = node['attr']
            elif node['attr']['type'] == 'id':
                break
        return value

    def visit_index(self, node):
        value = self.visit(node['value'])
        idx = self.visit(node['index'])
        if not isinstance(idx, int):
            raise RuntimeError('expected int')
        if not isinstance(value, (list, tuple)):
            raise RuntimeError('expected list object')
        return value[idx]

    def visit_raw(self, node):
        return node['value']

    def visit_if(self, node):
        test = self.visit(node['test'])
        if test:
            return self.visit(node['body'])
        elif node.get('else'):
            return self.visit(node['else'])

    def visit_for(self, node):
        result = []
        iter = self.visit(node['iter'])
        for i in iter:
            old_context = self.context
            new_context = {}
            new_context.update(self.context)
            new_context[node['target']['value']] = i
            self.context = new_context
            result.append(self.visit(node['body']))
            self.context = old_context
        return ''.join(result)

    def visit(self, node):
        if isinstance(node, list):
            result = []
            for n in node:
                visitor = getattr(self, 'visit_' + n['type'])
                result.append(visitor(n))
            return ''.join(map(str, result))

        visitor = getattr(self, 'visit_' + node['type'])
        return visitor(node)

    def eval(self, context):
        self.context = context
        x = self.visit(self.ast)
        return x


class Loader:
    def __init__(self):
        pass


def render(template, context=None):
    ast = Parser(template).parse()
    return Interpreter(ast).eval(context)

