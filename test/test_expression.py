from misai import render, filter


@filter
def test(a, b, c):
    return str(a) + str(b) + str(c)


@filter
def add(a, b):
    return a + b


def test_simple():
    assert render('{{ foo }}', {'foo': 'bar'}) == 'bar'
    assert render('{{ "foo" }}', {'foo': 'bar'}) == 'foo'
    assert render('{{ 1.2 }}', {'foo': 'bar'}) == '1.2'
    assert render('{{ 100 }}', {'foo': 'bar'}) == '100'


def test_pipe():
    assert render('{{ " foo " | strip | capitalize }}') == 'Foo'


def test_filter_params():
    assert render('{{ 1 | test: "2", "3" }}') == '123'
    assert render('{{ 100000 | add: 500 }}') == '100500'


def test_attr():
    assert render('{{ foo.bar }}', {'foo': {'bar': 'baz'}}) == 'baz'
    assert render('{{ foo.bar.baz }}', {'foo': {'bar': {'baz': 1}}}) == '1'

    assert render('{{ foo["bar"] }}', {'foo': {'bar': 'baz'}}) == 'baz'
    assert render('{{ foo["bar"][1] }}', {'foo': {'bar': [1, 2, 3]}}) == '2'


def test_precedence():
    assert render('{{ foo.bar | capitalize }}', {'foo': {'bar': 'baz'}}) == 'Baz'
