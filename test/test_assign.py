from misai import Template


def test_assign():
    t = Template('{{ #assign x = "foo" }}{{ x }}')
    assert t.render() == 'foo'


def test_assign_filter():
    t = Template('{{ #assign x = "foo" | capitalize }}{{ x }}')
    assert t.render() == 'Foo'
