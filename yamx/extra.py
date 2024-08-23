# not very supported pieces of functionality

from dataclasses import dataclass
from functools import partial
from typing import Any, Final, Optional, Union

from jinja2 import nodes

from yamx.constants import CONDITIONAL_KEY_PREFIX
from yamx.containers.data import (
    Condition,
    ConditionalData,
    ConditionalGroup,
    ConditionalMap,
    ConditionalSeq,
)
from yamx.loader.utils import get_jinja_env
from yamx.utils import strtobool

LIST_SYMBOL: Final[str] = "[]"


@dataclass(frozen=True)
class ResolvingContext:
    _data: dict[str, bool]

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


def extract_toggles(obj: Any) -> set[str]:
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


def _extract_toggles_from_condition(condition: Optional[Condition]) -> set[str]:
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


def _extract_toggles_from_if_node(node: nodes.Call) -> set[str]:
    """Current implementation supports operators `not`, `and` and `or`.
    Only following conditions are allowed:

    `defines.get("FEATURE_FLAG")`
    `toggles.FEATURE_FLAG`
    `toggles.get("FEATURE_FLAG")`
    `toggles["FEATURE_FLAG"]`
    `config_flags.NAME`
    `config_flags.get("NAME")`
    `config_flags["NAME"]`
    """
    if isinstance(node, nodes.Not):
        return _extract_toggles_from_if_node(node.node)
    elif isinstance(node, nodes.And) or isinstance(node, nodes.Or):
        left_toggles = _extract_toggles_from_if_node(node.left)
        right_toggles = _extract_toggles_from_if_node(node.right)
        return left_toggles | right_toggles
    # direct access, e.g. toggles.NAME
    elif isinstance(node, nodes.Getattr):
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


def resolve_toggles(obj: Any, context: dict[str, ResolvingContext]) -> Any:
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
    condition: Condition, context: dict[str, ResolvingContext]
) -> bool:
    """Resolve condition to boolean value"""
    env = get_jinja_env()
    # TODO: construct jinja ast if clause resolver
    jinja_ast = env.parse(
        f"{{% if {condition.raw_value} %}}True{{% else %}}False{{% endif %}}"
    )

    resolved = env.from_string(jinja_ast).render(context)

    return bool(strtobool(resolved))


def _config_by_key(config: dict, key: str):
    """Select sorting config specific to processed key"""
    return {k[1:]: v for k, v in config.items() if len(k) and k[0] == key}


def _extract_item_by_key(obj, key: Union[tuple[str, ...], str]):
    """Extract item by key"""
    # in case item is represented by conditional group - process "if" closure only
    if isinstance(obj, ConditionalGroup):
        # if conditional group is list-like, define it's order by the first item only
        if isinstance(obj.body, ConditionalSeq):
            return _extract_item_by_key(obj.body[0], key)
        return _extract_item_by_key(obj.body, key)

    if not isinstance(key, str) and len(key) == 1:
        key = key[0]

    if isinstance(key, str):
        # process simple keys
        if not isinstance(obj, ConditionalMap):
            raise ValueError(
                f"Key {key} defined in object which is not a ConditionalMap: {obj}"
            )
        if key not in obj:
            for v in obj.values():
                if isinstance(v, ConditionalGroup):
                    try:
                        return _extract_item_by_key(v, key)
                    except Exception:
                        continue
        else:
            return obj[key]
        raise KeyError(f"Key '{key}' not found in object: {obj}")

    # process complex keys
    if isinstance(obj, ConditionalMap):
        try:
            return _extract_item_by_key(obj[key[0]], key[1:])
        except KeyError:
            return None
    elif isinstance(obj, ConditionalSeq):
        if key[0] == LIST_SYMBOL:
            return [item[key[1]] for item in obj]
        return obj[key]
    else:
        raise ValueError(f"Unsupported object type: {type(obj)}")


def _key_order(key_value: tuple[str, Any], key_order: list[str]) -> Any:
    """Return order index of a key key/value pair"""
    key, value = key_value
    if key.startswith(CONDITIONAL_KEY_PREFIX) and isinstance(value, ConditionalGroup):
        # if first item is toggled, get the first key of the group
        # NOTE: assuming that nested dict is already sorted
        # NOTE: assuming that `value.body` is always a ConditionalMap
        return _key_order(next(iter(value.body.items())), key_order)
    elif key in key_order:
        return key_order.index(key)
    else:
        return len(key_order)


def sort_logical(obj: Any, config: dict) -> Any:
    """Perform logical sorting based on the provided structure"""
    if isinstance(obj, ConditionalData):
        return ConditionalData(sort_logical(obj.data, config))
    if isinstance(obj, ConditionalMap):
        nested_sort_map = {}

        for key, value in obj.items():
            # sort fields within conditional group same way as for the main dict
            if isinstance(value, ConditionalGroup):
                value = sort_logical(value, config)
            # if sorting config is empty, stop processing nested structures
            elif len(key_config := _config_by_key(config, key)):
                value = sort_logical(value, key_config)

            nested_sort_map[key] = value
        # sorting config for processed dict is under empty tuple key
        order_config = config.get(())
        if order_config:
            # raise in case item_order is used for dict
            if "item_order" in order_config:
                raise ValueError("'item_order' is not supported for dict type.")
            key_order = order_config.get("key_order", [])
            _get_key_order = partial(_key_order, key_order=key_order)
            res_dict = dict(
                sorted(
                    nested_sort_map.items(),
                    key=_get_key_order,
                )
            )
        else:
            res_dict = nested_sort_map

        return ConditionalMap(res_dict)
    elif isinstance(obj, ConditionalSeq):
        # sort nested structures first
        nested_sort_seq = []
        item_config = _config_by_key(config, LIST_SYMBOL)
        for item in obj:
            if isinstance(item, ConditionalGroup):
                item = sort_logical(item, config)
            elif item_config:
                item = sort_logical(item, item_config)
            nested_sort_seq.append(item)

        order_config = config.get(())
        if order_config:
            # raise in case key_order is used for list
            if "key_order" in order_config:
                raise ValueError("'key_order' is not supported for list type.")

            item_order = order_config.get("item_order", [])
            res_seq = sorted(
                nested_sort_seq,
                key=lambda item: [
                    _extract_item_by_key(item, key_conf["key"])
                    for key_conf in item_order
                ],
            )
        else:
            res_seq = nested_sort_seq

        return ConditionalSeq(res_seq)
    # preserve sort_config, just process each closure separately
    elif isinstance(obj, ConditionalGroup):
        return ConditionalGroup(
            condition=obj.condition,
            body=sort_logical(obj.body, config),
            else_body=sort_logical(obj.else_body, config),
            elif_bodies=tuple(
                ConditionalGroup(
                    condition=elif_body.condition,
                    body=sort_logical(elif_body.body, config),
                )
                for elif_body in obj.elif_bodies
            ),
        )
    else:
        return obj
