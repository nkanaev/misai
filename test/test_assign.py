from misai import Template


def test_assign():
    t = Template('{{ set x = "foo" }}{{ x }}')
    assert t.render() == 'foo'


def test_assign_filter():
    t = Template('{{ set x = "foo" | capitalize }}{{ x }}')
    assert t.render() == 'Foo'
