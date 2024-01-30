# not very supported pieces of functionality

from dataclasses import dataclass
from distutils.util import strtobool
from typing import Any, Dict, Optional, Set

from jinja2 import nodes

from yamx.containers.data import (
    Condition,
    ConditionalData,
    ConditionalGroup,
    ConditionalMap,
    ConditionalSeq,
)
from yamx.loader.utils import get_jinja_env


@dataclass(frozen=True)
class ResolvingContext:
    _data: Dict[str, bool]

    def __getattr__(self, attr_name):
        if attr_name in self._data:
            return self._data[attr_name]
        else:
            raise AttributeError(
                f"'ResolvingContext' object has no attribute '{attr_name}'"
            )

    def __getitem__(self, key: str) -> bool:
        return self._data[key]

    def get(self, key: str) -> bool:
        return self._data.get(key, False)

    def keys(self):
        return self._data.keys()


def extract_toggles(obj: Any) -> Set[str]:
    toggles = set()
    if isinstance(obj, ConditionalData):
        return extract_toggles(obj.data)
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
    """This method works only for particular condition format
    see _extract_toggle_from_if_node for exact logic definition
    """
    if condition is None:
        return set()
    env = get_jinja_env()
    jinja_ast = env.parse(f"{{% if {condition.raw_value} %}}{{% endif %}}")
    try:
        toggle_names = _extract_toggles_from_if_node(jinja_ast.body[0].test)
    except Exception:
        raise Exception(f"Unsupported toggle condition: {condition.raw_value}")
    return toggle_names


def _extract_toggles_from_if_node(if_test_node: nodes.Call) -> Set[str]:
    """Current implementation supports operators `not` and `and`.
    Only following conditions are allowed:

    `defines.get("FEATURE_FLAG")`
    `toggles.FEATURE_FLAG`
    `toggles.get("FEATURE_FLAG")`
    `toggles["FEATURE_FLAG"]`
    `config_flags.NAME`
    `config_flags.get("NAME")`
    `config_flags["NAME"]`
    """
    if isinstance(if_test_node, nodes.And):
        left_toggles = _extract_toggles_from_if_node(if_test_node.left)
        right_toggles = _extract_toggles_from_if_node(if_test_node.right)
        return left_toggles | right_toggles
    elif isinstance(if_test_node, nodes.Not):
        node = if_test_node.node
    else:
        node = if_test_node

    # direct access, e.g. toggles.NAME
    if isinstance(node, nodes.Getattr):
        name = node.node.name
        value = node.attr
    # getitem access, e.g. toggles[]
    elif isinstance(node, nodes.Getitem):
        name = node.node.name
        value = node.arg.value
    # get access, e.g. toggles.get()
    elif isinstance(node, nodes.Call) and node.node.attr == "get":
        name = node.node.node.name
        value = node.args[0].value
    else:
        raise Exception

    assert name in ["defines", "toggles", "config_flags"]
    return {
        value,
    }


def resolve_toggles(obj: Any, context: Dict[str, ResolvingContext]) -> Any:
    if isinstance(obj, ConditionalData):
        return resolve_toggles(obj.data, context)
    elif isinstance(obj, ConditionalMap):
        res_dict = {}
        for key, val in obj.items():
            if isinstance(val, ConditionalGroup):
                res_val = resolve_toggles(val, context)
                if res_val:
                    res_dict.update(res_val)
            else:
                res_dict[key] = resolve_toggles(val, context)
        return res_dict

    elif isinstance(obj, ConditionalSeq):
        res_seq = []
        for item in obj:
            if isinstance(item, ConditionalGroup):
                res_item = resolve_toggles(item, context)
                if res_item:
                    res_seq.extend(res_item)
            else:
                res_seq.append(resolve_toggles(item, context))
        return res_seq

    elif isinstance(obj, ConditionalGroup):
        toggles = _extract_toggles_from_condition(obj.condition)

        assert toggles.issubset(
            set(context["defines"].keys())
        ), f"Toggle definition for {toggles} is missing."

        assert obj.condition
        if resolve_condition(obj.condition, context):
            # TODO: split elif body from regular condition body
            return resolve_toggles(obj.body, context)
        for elif_body in obj.elif_bodies:
            assert elif_body.condition
            if resolve_condition(elif_body.condition, context):
                return resolve_toggles(elif_body.body, context)
        if obj.else_body:
            return resolve_toggles(obj.else_body, context)
    else:
        return obj


def resolve_condition(
    condition: Condition, context: Dict[str, ResolvingContext]
) -> bool:
    """Resolve condition to boolean value"""
    env = get_jinja_env()
    # TODO: construct jinja ast if clause resolver
    jinja_ast = env.parse(
        f"{{% if {condition.raw_value} %}}True{{% else %}}False{{% endif %}}"
    )

    resolved = env.from_string(jinja_ast).render(context)

    return bool(strtobool(resolved))
