from misai import Template


def test_if():
    template = Template('{{ #if 1 == 1 }}foo{{ #endif }}')
    assert template.render() == 'foo'


def test_if_else():
    template = Template('{{ #if 1 == 2 }}foo{{ #else }}bar{{ #endif }}')
    assert template.render() == 'bar'


def test_if_elseif():
    template = Template('{{ #if 1 == 2 }}foo{{ #elseif 1 == 1 }}bar{{ #endif }}')
    assert template.render() == 'bar'


def test_if_elseif_else():
    template = Template('''{{ #if 1 == 2 }}foo{{ #elseif 1 == 3 }}bar{{ #else }}baz{{ #endif }}''')
    assert template.render() == 'baz'
