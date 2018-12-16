from misai import Lexer, ExpressionNode, Context, filter


@filter
def test(a, b, c):
    return str(a) + str(b) + str(c)


@filter
def add(a, b):
    return a + b


def expr(template, params=None, mode='simple'):
    lexer = Lexer(template)
    lexer.consume('ldelim')
    node = ExpressionNode().parse(lexer)
    lexer.consume('rdelim')
    return node.render(Context(params or {}))


def test_simple():
    assert expr('{{ foo }}', {'foo': 'bar'}) == 'bar'
    assert expr('{{ "foo" }}', {'foo': 'bar'}) == 'foo'
    assert expr('{{ 1.2 }}', {'foo': 'bar'}) == '1.2'
    assert expr('{{ 100 }}', {'foo': 'bar'}) == '100'


def test_pipe():
    assert expr('{{ " foo " | strip | capitalize }}') == 'Foo'


def test_filter_params():
    assert expr('{{ 1 | test("2", "3") }}') == '123'
    assert expr('{{ 100000 | add(500) }}') == '100500'


def test_attr():
    assert expr('{{ foo.bar }}', {'foo': {'bar': 'baz'}}) == 'baz'
    assert expr('{{ foo.bar.baz }}', {'foo': {'bar': {'baz': 1}}}) == '1'

    assert expr('{{ foo["bar"] }}', {'foo': {'bar': 'baz'}}) == 'baz'
    assert expr('{{ foo["bar"][1] }}', {'foo': {'bar': [1, 2, 3]}}) == '2'
