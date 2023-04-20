from typing import Any

from yamjinx.constants import ToggledBlockType
from yamjinx.containers import ConditionalGroup, ConditionalNode, ToggledMap, ToggledSeq


def group_toggled_data(data: Any) -> Any:
    if isinstance(data, ToggledMap):
        return _parse_toggled_map_data(data)
    elif isinstance(data, ToggledSeq):
        return _parse_toggled_seq_data(data)

    return data


def _parse_toggled_seq_data(seq: ToggledSeq) -> ToggledSeq:
    """Parses toggled key-values into ConditionalGroup objects

    NOTE: here ToggledMap object can represent 2 different structures
    1. toggled list item
    2. list item that represents toggled map
    """
    if len(seq) == 0:
        return seq
    new_seq = ToggledSeq()
    seq.copy_attributes(new_seq)
    prev_item = None

    for item in seq:
        if not isinstance(item, ConditionalNode):
            if isinstance(item, ToggledMap):
                item = _parse_toggled_map_data(item)
            elif isinstance(item, ToggledSeq):
                item = _parse_toggled_seq_data(item)

            new_item = item
        elif (
            not isinstance(prev_item, ConditionalGroup)
            or item.typ is ToggledBlockType.if_
        ):
            new_item = ConditionalGroup(
                body=group_toggled_data(item.data), condition=item.condition
            )
        # otherwise group prev item with new
        else:
            # TODO: update indexes of all following comments in new_seq.ca
            prev_item = prev_item.with_conditional_block(
                data=group_toggled_data(item.data),
                typ=item.typ,
                condition=item.condition,
            )
            continue

        # if it's not the first item
        if prev_item is not None:
            new_seq.append(prev_item)
        # remember prev element for following iterations
        prev_item = new_item

    new_seq.append(prev_item)

    return new_seq


def _parse_toggled_map_data(mapping: ToggledMap) -> ToggledMap:
    """Parses toggled key-values into ConditionalGroup objects"""
    if len(mapping) == 0:
        return mapping

    new_map = ToggledMap()
    # preserve original comment attributes
    mapping.copy_attributes(new_map)
    prev_item = None

    for (key, value) in mapping.items():
        if not isinstance(value, ConditionalNode):
            if isinstance(value, ToggledMap):
                value = _parse_toggled_map_data(value)
            elif isinstance(value, ToggledSeq):
                value = _parse_toggled_seq_data(value)
            new_item = (key, value)
        elif (
            not prev_item
            or not isinstance(prev_item[1], ConditionalGroup)
            or value.typ is ToggledBlockType.if_
        ):
            new_item = (
                key,
                ConditionalGroup(
                    body=group_toggled_data(value.data), condition=value.condition
                ),
            )
        # otherwise group prev item with new
        else:
            # remove key of prev item from the mapping
            prev_item = (
                key,
                prev_item[1].with_conditional_block(
                    data=group_toggled_data(value.data),
                    typ=value.typ,
                    condition=value.condition,
                ),
            )
            continue

        # if it's not the first item
        if prev_item is not None:
            (key, value) = prev_item
            new_map[key] = value

        # remember prev element for following iterations
        prev_item = new_item

    assert isinstance(prev_item, tuple)
    (key, value) = prev_item
    new_map[key] = value
    return new_map
