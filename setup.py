# coding: utf-8
from setuptools import setup


long_description = open('readme.rst').read()


setup(
    name='misai',
    version='0.1.0',
    description='simple template engine',
    long_description=long_description,
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
)
