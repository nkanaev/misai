# Misai

Simple template engine inspired by mustache and jinja.

# Example

    {{#if logged_in}}
        {{#for user in users}}
            {{ user.name }}
        {{#endfor}}
    {{#endif}}

