from misai import Template


def test_if():
    template = Template('{{ #if 1 == 1 }}foo{{ #endif }}')
    assert template.render() == 'foo'


def test_if_else():
    template = Template('{{ #if 1 == 2 }}foo{{ #else }}bar{{ #endif }}')
    assert template.render() == 'bar'


def test_if_elseif():
    template = Template(
        '{{ #if 1 == 2 }}foo'
        '{{ #elseif 1 == 1 }}bar{{ #endif }}')
    assert template.render() == 'bar'


def test_if_elseif_else():
    template = Template(
        '{{ #if 1 == 2 }}foo'
        '{{ #elseif 1 == 3 }}bar'
        '{{ #else }}baz{{ #endif }}')
    assert template.render() == 'baz'


def test_comparison():
    test_cases = [
        ['{{#if 1!=2}}foo{{#endif}}', 'foo'],
        ['{{#if 2<=2}}foo{{#endif}}', 'foo'],
        ['{{#if 2>=2}}foo{{#endif}}', 'foo'],
        ['{{#if 1<2}}foo{{#endif}}', 'foo'],
        ['{{#if 2>1}}foo{{#endif}}', 'foo'],
    ]
    for source, expected in test_cases:
        template = Template(source)
        assert template.render() == expected, source


def test_and_or():
    test_cases = [
        ['{{#if 1==1 and 2==2}}foo{{#endif}}', 'foo'],
        ['{{#if 1==1 and 1==2}}foo{{#endif}}', ''],
        ['{{#if 1==1 or 1==2}}foo{{#endif}}', 'foo'],
        ['{{#if 1==2 or 1==2}}foo{{#endif}}', ''],
    ]

    for source, expected in test_cases:
        template = Template(source)
        assert template.render() == expected, source
