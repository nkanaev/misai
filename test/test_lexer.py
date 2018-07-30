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
    lexer = Lexer(r'{{ > < == != <= >= or and + - * / % }}')
    tokens = [
        Token('ldelim', '{{', 0),
        Token('binop', '>', 3),
        Token('binop', '<', 5),
        Token('binop', '==', 7),
        Token('binop', '!=', 10),
        Token('binop', '<=', 13),
        Token('binop', '>=', 16),
        Token('binop', 'or', 19),
        Token('binop', 'and', 22),
        Token('binop', '+', 26),
        Token('binop', '-', 28),
        Token('binop', '*', 30),
        Token('binop', '/', 32),
        Token('binop', '%', 34),
        Token('rdelim', '}}', 36),
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
