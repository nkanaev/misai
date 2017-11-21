misai
=====

Simple template engine inspired by mustache and jinja.

example
-------

::

    {{ #if logged_in }}
        {{ #for user : users }}
            {{ user.name }}
        {{ #endfor }}
    {{ #endif }}

