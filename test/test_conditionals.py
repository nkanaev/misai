from misai import Template


def test_if():
    template = Template('{{ #if 1 == 1 }}foo{{ #end }}')
    assert template.render() == 'foo'


def test_if_else():
    template = Template('{{ #if 1 == 2 }}foo{{ #else }}bar{{ #end }}')
    assert template.render() == 'bar'


def test_if_elif():
    template = Template(
        '{{ #if 1 == 2 }}foo'
        '{{ #elif 1 == 1 }}bar{{ #end }}')
    assert template.render() == 'bar'


def test_if_elif_else():
    template = Template(
        '{{ #if 1 == 2 }}foo'
        '{{ #elif 1 == 3 }}bar'
        '{{ #else }}baz{{ #end }}')
    assert template.render() == 'baz'


def test_comparison():
    test_cases = [
        ['{{#if 1!=2}}foo{{#end}}', 'foo'],
        ['{{#if 2<=2}}foo{{#end}}', 'foo'],
        ['{{#if 2>=2}}foo{{#end}}', 'foo'],
        ['{{#if 1<2}}foo{{#end}}', 'foo'],
        ['{{#if 2>1}}foo{{#end}}', 'foo'],
    ]
    for source, expected in test_cases:
        template = Template(source)
        assert template.render() == expected, source


def test_and_or():
    test_cases = [
        ['{{#if 1==1 and 2==2}}foo{{#end}}', 'foo'],
        ['{{#if 1==1 and 1==2}}foo{{#end}}', ''],
        ['{{#if 1==1 or 1==2}}foo{{#end}}', 'foo'],
        ['{{#if 1==2 or 1==2}}foo{{#end}}', ''],
    ]

    for source, expected in test_cases:
        template = Template(source)
        assert template.render() == expected, source
