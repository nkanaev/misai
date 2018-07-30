import re
import collections


Token = collections.namedtuple('Token', ['type', 'value', 'pos'])


class TemplateSyntaxError(Exception):
    pass


class Lexer:
    def __init__(self, content):
        self.content = content
        self.cache = collections.deque()
        self.tokens = list(self.tokenize())
        self.idx = 0

    def consume(self, token_type):
        token = self.pop()
        if token.type != token_type:
            raise TemplateSyntaxError(
                'expected {}, got {}'.format(token_type, token.type),
                source=self.source,
                pos=token.pos)
        return token

    def lookup(self):
        return self.tokens[self.idx]

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

                (c(r'\.'), 'dot'),
                (c(r'\|'), 'pipe'),
                (c(r':'), 'colon'),
                (c(r'\['), 'lsquare'),
                (c(r'\]'), 'rsquare'),
                (c(r'==|!=|<=|>=|<|>|&&'), 'binop'),
                (c(r'\b(and|or)\b'), 'binop'),
                (c(r'\+|\-|\*|\/|\%'), None),

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
        while pos < len(self.content):
            for regex, name in rules['block' if inside_delim else 'root']:
                m = regex.match(self.content, pos)
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

                    print('shit', name, repr(match), repr(value), pos_prev)

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
                msg = 'unexpected char {}'.format(repr(self.content[pos]))
                raise TemplateSyntaxError(msg, pos=pos, content=self.content)


class Node:
    def __init__(self):
        self.children = []

    def parse(self, tokens):
        raise NotImplementedError

    def reunder(self, context):
        raise NotImplementedError


class BinOp(Node):
    def parse(self, tokens):
        pass

    def render(self, context):
        pass


class Document(Node):
    def parse(self, tokens):
        pass

    def render(self, context):
        with context.stack() as subcontext:
            pass


class Template:
    def __init__(self, source):
        self.source = source
        self.root = Document.parse(Lexer(self.source))

    def render(self, **context):
        return self.root.render(Context(context))


def render(content, context):
    return Template(content).render(**context)
