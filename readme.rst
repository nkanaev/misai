misai
=====

Simple template engine inspired by mustache and jinja.

example
-------

::

    {{ #if logged_in }}
        {{ #for user : users }}
            {{ user.name }}
        {{ #end }}
    {{ #end }}


tests
-----

.. image:: https://travis-ci.org/nkanaev/misai.svg?branch=master
    :target: https://travis-ci.org/nkanaev/misai
