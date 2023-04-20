# not very supported pieces of functionality

from typing import Any, Set, Tuple

from jinja2 import nodes

from yamjinx.containers.data import ToggledGroup, ToggledMap, ToggledSeq


def extract_toggles(obj: Any, toggles: Set[str] = set()):
    if isinstance(obj, ToggledMap):
        for value in obj.values():
            toggles |= extract_toggles(value)
    elif isinstance(obj, ToggledSeq):
        for value in obj:
            toggles |= extract_toggles(value)
    elif isinstance(obj, ToggledGroup):
        toggles |= set(obj.toggles_)
        toggles |= extract_toggles(obj.body)
        toggles |= extract_toggles(obj.else_body)
        for elif_body in obj.elif_bodies or []:
            toggles |= extract_toggles(elif_body)
    else:
        return toggles

    return toggles


def _extract_toggle_from_if_node(if_node) -> Tuple[str, bool]:
    # we have negation in condition
    if isinstance(if_node.test, nodes.Not):
        return if_node.test.node.args[0].value, False
    return if_node.test.args[0].value, True
