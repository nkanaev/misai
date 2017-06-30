import re
import collections


Token = collections.namedtuple('Token', ['type', 'name', 'pos'])


class TemplateSyntaxError(Exception): pass


def itertoken(template, ldelim='{{', rdelim='}}'):
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
            (c(r'\.'), 'dot'),
            (c(r'\['), 'lsquare'),
            (c(r'\]'), 'rsquare'),
            (c(r'".+"'), 'str'),
            (c(r'#if'), 'keyword'),
            (c(r'#for'), 'keyword'),
            (c(r'#elseif'), 'keyword'),
            (c(r'#else'), 'keyword'),
            (c(r'#endif'), 'keyword'),
            (c(r'#endfor'), 'keyword'),
            (c(r':'), 'colon'),
            (c(r'\+|\-|\*|\/'), 'operator'),
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
                msg = '{} yielded empty string'.format(regex)
                raise TemplateSyntaxError(msg)

            pos = m.end()

            if not inside_delim:
                if name != 'comment' and m.group(1):
                    yield Token('raw', m.group(1), pos)
                if name == 'ldelim':
                    inside_delim = True
                    yield Token('ldelim', ldelim, pos)
                break
            else:
                if name != 'ws':
                    yield Token(name, m.group(), pos)
                    if name == 'rdelim':
                        inside_delim = False
                break
        else:
            msg = 'unexpected char {} at {}'.format(repr(template[pos]), pos)
            raise TemplateSyntaxError(msg)


class Parser:
    def __init__(self, template):
        self.template = template
        self.tokeniter = itertoken(template)
        self.cache = collections.deque()

    def fail(self, msg):
        raise TemplateSyntaxError(msg)

    @property
    def current_token(self):
        if not self.cache:
            self.cache.append(next(self.tokeniter, Token(None, None, None)))
        return self.cache[0]

    def next_token(self):
        if self.cache:
            return self.cache.popleft()
        return next(self.tokeniter, None)

    def expect_token(self, token_type):
        if self.current_token.type != token_type:
            self.fail('expected {}'.format(token_type))

    def parse_if(self):
        result = node = {'type': 'if'}
        while 1:
            node['test'] = self.parse_expr()
            self.expect_token('rdelim')
            self.next_token()
            node['body'] = self.subparse(until=['#else', '#elseif', '#endif'])
            if self.current_token.name == '#elseif':
                self.next_token()
                subnode = {'type': 'if'}
                node['else'] = subnode
                node = subnode
                continue
            elif self.current_token.name == '#else':
                self.next_token()
                self.expect_token('rdelim')
                self.next_token()
                node['else'] = self.subparse(until=['#endif'])
                self.next_token()
            elif self.current_token.name == '#endif':
                self.next_token()
            break
        return result

    def parse_for(self):
        result = {'type': 'for'}
        result['target'] = self.parse_id()
        self.expect_token('colon')
        self.next_token()
        result['iter'] = self.parse_id()
        self.expect_token('rdelim')
        self.next_token()
        result['body'] = self.subparse(until=['#endfor'])
        self.next_token()
        return result

    def parse_expr(self):
        return self.parse_id()

    def parse_id(self):
        if self.current_token.type != 'id':
            self.fail('Unexpected token, expecting id')
        node = self.next_token()
        return {'type': 'id', 'value': node.name}

    def subparse(self, until=None):
        nodes = []
        while True:
            if self.current_token.type == 'raw':
                nodes.append({'type': 'raw', 'value': self.next_token().name})
            elif self.current_token.type == 'ldelim':
                self.next_token()  # ignore left delimiter
                if self.current_token.type == 'keyword':
                    if until and self.current_token.name in until:
                        return nodes
                    elif self.current_token.name == '#if':
                        self.next_token()
                        nodes.append(self.parse_if())
                    elif self.current_token.name == '#for':
                        self.next_token()
                        nodes.append(self.parse_for())
                else:
                    nodes.append(self.parse_expr())

                if self.current_token.type == None:
                    break
                self.expect_token('rdelim')
                self.next_token()  # ignore right delimiter
            elif self.current_token.type == None:
                break
            else:
                self.fail('unknown parser error')
        return nodes

    def parse(self):
        return {'type': 'body', 'nodes': self.subparse()}


class Interpreter:
    def __init__(self, tree):
        self.tree = tree

    def visit_nodes(self, nodes):
        result = ''
        for subnode in nodes:
            result += str(getattr(self, 'visit_' + subnode['type'])(subnode))
        return result

    def visit_expr(self, node):
        return self.visit_id(node)

    def visit_id(self, node):
        return self.context[node['value']]

    def visit_raw(self, node):
        return node['value']

    def visit_if(self, node):
        test = self.visit_expr(node['test'])
        if test:
            return self.visit_nodes(node['body'])
        elif node.get('else'):
            return self.visit_nodes(node['else'])

    def visit_for(self, node):
        result = ''
        iter = self.visit_expr(node['iter'])
        for i in iter:
            old_context = self.context
            new_context = {}
            new_context.update(self.context)
            new_context[node['target']['value']] = i
            self.context = new_context
            result += self.visit_nodes(node['body'])
            self.context = old_context
        return result

    def visit_body(self, node):
        return self.visit_nodes(node['nodes'])

    def run(self, context):
        self.context = context
        return self.visit_body(self.tree)


def parse(template):
    return Parser(template).parse()


def render(template, context=None):
    tree = parse(template)
    return Interpreter(tree).run(context)

