import os

from misai import Loader


here = os.path.dirname(os.path.abspath(__file__))
tmpl_dir = os.path.join(here, 'templates')


def test_add_absolute():
    loader = Loader(tmpl_dir)
    result = loader.get('test/foo.txt').render()
    assert result == 'foobar'


def test_add_relative_with_params():
    loader = Loader(tmpl_dir)
    result = loader.get('base.txt').render(endword='!!!')
    assert result == 'onetwothree!!!'
