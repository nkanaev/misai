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

.. image:: https://github.com/nkanaev/misai/workflows/test/badge.svg
    :target: https://github.com/nkanaev/misai/actions
