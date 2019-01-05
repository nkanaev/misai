import misai
from textwrap import dedent


def test_section_clean():
    assert misai.render(' | {{#if 1}}\t|\t{{#end}} | \n') == ' | \t|\t | \n'
    assert misai.render(' | {{#if 1}} {{ "" }}\n {{#end}} | \n') == ' |  \n  | \n'
    assert misai.render(' {{#if 1}}YES{{#end}}\n {{#if 1}}GOOD{{#end}}\n') == ' YES\n GOOD\n'
    assert misai.render(dedent('''\
        |
        | This Is
        {{#if 1}}
        |
        {{#end}}
        | A Line''')) == dedent('''\
        |
        | This Is
        |
        | A Line''')

    assert misai.render(dedent('''\
        |
        | This Is
            {{#if 1}}
        |
           {{#end}}  \t
        | A Line''')) == dedent('''\
        |
        | This Is
        |
        | A Line''')
    assert misai.render('|\r\n{{#if 1}}\r\n{{#end}}\r\n|') == '|\r\n|'
    assert misai.render('  {{#if 1}}\n#{{#end}}\n/') == '#\n/'
    assert misai.render('#{{#if 1}}\n/\n  {{#end}}') == '#\n/\n'
    assert misai.render('|{{#if 1}}={{#end}}|') == '|=|'

    assert misai.render(' \t{{ foo }}\t ', {'foo': 'bar'}) == ' \tbar\t '
