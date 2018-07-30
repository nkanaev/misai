from misai import Lexer, Token


def test_delimiters():
    lexer = Lexer('{{ place }}')
    tokens = [
        Token('ldelim', '{{', 0),
        Token('id', 'place', 3),
        Token('rdelim', '}}', 9),
    ]
    assert tokens == lexer.tokens


def test_literals():
    lexer = Lexer(r'{{ 1 2.5 "test" "\"test\"" }}')
    tokens = [
        Token('ldelim', '{{', 0),
        Token('int', 1, 3),
        Token('float', 2.5, 5),
        Token('str', "test", 9),
        Token('str', '"test"', 16),
        Token('rdelim', '}}', 27),
    ]
    assert tokens == lexer.tokens
