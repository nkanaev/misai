from misai import Template


def test_basic():
    template = Template('hello {{ place }}!')
    assert 'hello world!' == template.render(place='world')
