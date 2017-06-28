import misai
import textwrap


def test_var():
    template = 'hello {{ place }}'
    misai.parse(template)


def test_conditional():
    template = textwrap.dedent('''\
        {{ #if yes }}
            yes
        {{ #elseif maybe }}
            maybe
        {{ #else }}
            no
        {{ #endif }}
    ''')
    misai.parse(template)

def test_loop():
    template = textwrap.dedent('''\
        {{ #for item : items }}
            * {{ item }}
        {{ #endfor }}
    ''')
    print(misai.parse(template))

