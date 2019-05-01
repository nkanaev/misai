# coding: utf-8
from setuptools import setup
from setuptools.command.test import test as TestCommand


class PyTestCommand(TestCommand):
    user_options = [("pytest-args=", "a", "Arguments to pass to pytest")]

    def run_tests(self):
        import sys, pytest
        sys.exit(pytest.main([]))


setup(
    name='misai',
    version='0.1.1',
    description='simple template engine',
    long_description=open('readme.rst').read(),
    url='https://github.com/nkanaev/misai',
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    author='Nazar Kanaev',
    author_email='nkanaev@live.com',
    py_modules=['misai'],
    package_data={'': ['readme.rst']},
    include_package_data=True,
    test_suite='test',
    tests_require=['pytest'],
    cmdclass={"test": PyTestCommand},
)
