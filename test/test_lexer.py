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
    lexer = Lexer(r'''{{ 1 2.5 "test" "\"test\"" 'x' 'x\'s' }}''')
    tokens = [
        Token('ldelim', '{{', 0),
        Token('int', 1, 3),
        Token('float', 2.5, 5),
        Token('str', "test", 9),
        Token('str', '"test"', 16),
        Token('str', 'x', 27),
        Token('str', "x's", 31),
        Token('rdelim', '}}', 38),
    ]
    assert tokens == lexer.tokens


def test_comparison():
    lexer = Lexer(r'{{ > < == != <= >= or and }}')
    tokens = [
        Token('ldelim', '{{', 0),
        Token('comp', '>', 3),
        Token('comp', '<', 5),
        Token('comp', '==', 7),
        Token('comp', '!=', 10),
        Token('comp', '<=', 13),
        Token('comp', '>=', 16),
        Token('logic', 'or', 19),
        Token('logic', 'and', 22),
        Token('rdelim', '}}', 26),
    ]
    assert tokens == lexer.tokens


def test_ids():
    lexer = Lexer(r'{{ hello andrew oregon }}')
    tokens = [
        Token('ldelim', '{{', 0),
        Token('id', 'hello', 3),
        Token('id', 'andrew', 9),
        Token('id', 'oregon', 16),
        Token('rdelim', '}}', 23),
    ]
    assert tokens == lexer.tokens


def test_keywords():
    lexer = Lexer(r'{{ #for #endfor }}')
    tokens = [
        Token('ldelim', '{{', 0),
        Token('keyword', '#for', 3),
        Token('keyword', '#endfor', 8),
        Token('rdelim', '}}', 16),
    ]
    assert tokens == lexer.tokens
