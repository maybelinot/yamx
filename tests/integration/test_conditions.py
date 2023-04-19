import pytest

from yamjinx.loader.condition import extract_condition
from yamjinx.loader.utils import get_jinja_env


@pytest.mark.parametrize(
    "original_condition",
    [
        # different toggle names
        'defines.get("toggle_a")',
        'defines.get("toggle_b")',
        # literals
        "1",
        '"1"',
        "True",
        "[]",
        '{"a": 1}',
        "set([1, 2])",
        # and / or conditions
        "1 and 1",
        "1 or 1",
        # # and or with precedence
        "(1 or 1) and 1",
        "1 or 1 and 1",
        "1 and (1 or 1)",
        "1 and 1 or 1",
        # # # and/or with negation
        "not 1 and 1",
        "1 and not 1",
        "not 1 or 1",
        "1 or not 1",
        # unops
        # # negation
        "not 1",
        "not(1 and 1)",
        "not(1 or 1)",
        # neg
        "- 1",
        "-(1 and 1)",
        "-(1 or 1)",
        "-(1 / 1)",
        # binops
        "1 - - 1",
        "1 - + 1",
        "1 / not(1)",
    ],
)
def test_condition_representer(original_condition):

    data = f"""
    pre-conditional text
    {{% if {original_condition} %}}
    conditional text
    {{% endif %}}
    postconditional text
    """
    env = get_jinja_env()
    jinja_ast = env.parse(data)

    ast_node = jinja_ast.body[1].test

    condition = extract_condition(ast_node, env)

    assert condition == original_condition
