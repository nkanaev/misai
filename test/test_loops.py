from misai import Template, filter


@filter
def reverse(items):
    return reversed(items)


def test_simple():
    t = Template('{{ for a in b }}{{ a }}{{ end }}')
    assert t.render(b=['foo', 'bar']) == 'foobar'


def test_loop_filters():
    t = Template('{{ for a in b | reverse }}{{ a }}{{ end }}')
    assert t.render(b=['foo', 'bar']) == 'barfoo'


def test_scopes():
    t = Template(
        '{{ set foo = "baz" }}'
        '{{ for foo in items }}{{ foo }}{{ end }}'
        '{{ foo }}')
    assert t.render(items=['bar']) == 'barbaz'
