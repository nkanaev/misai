from misai import Lexer, ExpressionNode, Context


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
