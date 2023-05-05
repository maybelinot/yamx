# not very supported pieces of functionality

from typing import Any, Optional, Set

from jinja2 import nodes

from yamx.containers.data import (
    Condition,
    ConditionalGroup,
    ConditionalMap,
    ConditionalSeq,
)
from yamx.loader.utils import get_jinja_env


def extract_toggles(obj: Any, toggles: Set[str] = set()):
    if isinstance(obj, ConditionalMap):
        for value in obj.values():
            toggles |= extract_toggles(value)
    elif isinstance(obj, ConditionalSeq):
        for value in obj:
            toggles |= extract_toggles(value)
    elif isinstance(obj, ConditionalGroup):
        toggles |= _extract_toggles_from_condition(obj.condition)
        toggles |= extract_toggles(obj.body)
        toggles |= extract_toggles(obj.else_body)
        for elif_body in obj.elif_bodies or []:
            toggles |= extract_toggles(elif_body)
    else:
        return toggles

    return toggles


def _extract_toggles_from_condition(condition: Optional[Condition]) -> Set[str]:
    """This method works only for particular condition format"""
    if condition is None:
        return set()
    env = get_jinja_env()
    jinja_ast = env.parse(f"{{% if {condition.raw_value} %}}{{% endif %}}")
    return {
        _extract_toggle_from_if_node(jinja_ast.body[0].test),
    }


def _extract_toggle_from_if_node(if_test_node: nodes.Call) -> str:
    # we have negation in condition
    if isinstance(if_test_node, nodes.Not):
        return if_test_node.node.args[0].value
    return if_test_node.args[0].value
