import re


class TemplateSyntaxError(Exception): pass


def itertoken(template, ldelim='{{', rdelim='}}'):
    c = re.compile
    ldelim = re.escape(ldelim)
    rdelim = re.escape(rdelim)
    rules = {
        'root': [
            (c(r'{#.+?#}', re.S), 'comment'),
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
            (c(r'#else'), 'keyword'),
            (c(r'#elseif'), 'keyword'),
            (c(r'#endif'), 'keyword'),
            (c(r'#endfor'), 'keyword'),
            (c(r'in'), 'keyword'),
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
                    yield pos, 'raw', m.group(1)
                if name == 'ldelim':
                    inside_delim = True
                    yield pos, 'ldelim', '{{'
                break
            else:
                if name != 'ws':
                    yield pos, name, m.group()
                    if name == 'rdelim':
                        inside_delim = False
                break
        else:
            msg = 'unexpected char {} at {}'.format(repr(template[pos]), pos)
            raise TemplateSyntaxError(msg)


def render(template, context=None):
    return ''

