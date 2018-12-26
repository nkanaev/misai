from misai import htmlescape, render, Template


def test_escape():
    assert Template('<script>{{ foo }}', ).render(foo='<script>') == '<script><script>'
    assert Template('<script>{{ foo }}', formatter=htmlescape).render(foo='<script>') == '<script>&lt;script&gt;'
