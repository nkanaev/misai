from misai import render as r
from textwrap import dedent as d


def test_variables():
    data = {'place': 'world'}
    tmpl = 'hello {{ place }}'
    result = 'hello world'
    assert r(tmpl, data) == result

    data = {'foo': {'bar': 'baz'}}
    tmpl = '{{ foo.bar }}'
    result = 'baz'
    assert r(tmpl, data) == result

    data = {'foo': [0, 1, 2]}
    tmpl = '{{ foo[1] }}'
    result = '1'
    assert r(tmpl, data) == result

    data = {'foo': {'bar': [0, 1, 2]}}
    tmpl = '{{ foo.bar[1] }}'
    result = '1'
    assert r(tmpl, data) == result

    data = {'foo': [{'bar': 'baz'}]}
    tmpl = '{{ foo[0].bar }}'
    result = 'baz'
    assert r(tmpl, data) == result


def test_expressions():
    data = {}
    tmpl = '{{ 1 + 2 }}'
    result = '3'
    assert r(tmpl, data) == result

    data = {}
    tmpl = '{{ 2 * 3 }}'
    result = '6'
    assert r(tmpl, data) == result

    data = {}
    tmpl = '{{ 1 + 2 * 3 / 4 }}'
    result = '2.5'
    assert r(tmpl, data) == result


def test_conditionals():
    data = {'foo': True}
    tmpl = '{{ #if foo }}yes{{ #else }}no{{ #endif }}'
    result = 'yes'
    assert r(tmpl, data) == result

    data = {}
    tmpl = '{{ #if 1 + 1 == 2 }}yes{{ #endif }}'
    result = 'yes'
    assert r(tmpl, data) == result

    data = {'foo': False}
    tmpl = '{{ #if foo }}yes{{ #else }}no{{ #endif }}'
    result = 'no'
    assert r(tmpl, data) == result

    data = {}
    tmpl = d('''\
        {{ #if 1 }}
        yes
        {{ #endif }}
    ''')
    result = 'yes'
    assert r(tmpl, data) == result, 'tag lines must be stripped'


def test_loops():
    data = {'nums': [1, 2, 3]}
    tmpl = '{{ #for n : nums }}{{ n }}{{ #endfor }}'
    result = '123'
    assert r(tmpl, data) == result

    tmpl = d('''\
        {{ #for n : nums }}
        {{ n }}
        {{ #endfor }}
    ''')
    result = d('''\
        1
        2
        3
    ''')
    assert r(tmpl, data) == result, 'tag lines must be stripped'


if __name__ == '__main__':
    test_variables()
    test_conditionals()
    test_loops()

