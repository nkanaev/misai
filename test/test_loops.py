from misai import Template, filter


@filter
def reverse(items):
    return reversed(items)


def test_simple():
    t = Template('{{ #for a : b }}{{ a }}{{ #endfor }}')
    assert t.render(b=['foo', 'bar']) == 'foobar'


def test_loop_filters():
    t = Template('{{ #for a : b|reverse }}{{ a }}{{ #endfor }}')
    assert t.render(b=['foo', 'bar']) == 'barfoo'
