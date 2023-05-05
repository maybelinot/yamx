from typing import Any

from yamx.constants import ConditionalBlockType
from yamx.containers import (
    ConditionalBlock,
    ConditionalGroup,
    ConditionalMap,
    ConditionalSeq,
)


def group_conditional_blocks(data: Any) -> Any:
    if isinstance(data, ConditionalMap):
        return _group_map_conditional_blocks(data)
    elif isinstance(data, ConditionalSeq):
        return _group_seq_conditional_blocks(data)

    return data


def _group_seq_conditional_blocks(seq: ConditionalSeq) -> ConditionalSeq:
    """Groups ConditionalBlock items into ConditionalGroup objects"""
    if len(seq) == 0:
        return seq
    new_seq = ConditionalSeq()
    seq.copy_attributes(new_seq)
    prev_item = None

    for item in seq:
        if not isinstance(item, ConditionalBlock):
            if isinstance(item, ConditionalMap):
                item = _group_map_conditional_blocks(item)
            elif isinstance(item, ConditionalSeq):
                item = _group_seq_conditional_blocks(item)

            new_item = item
        elif (
            not isinstance(prev_item, ConditionalGroup)
            or item.typ is ConditionalBlockType.if_
        ):
            new_item = ConditionalGroup(
                body=group_conditional_blocks(item.data), condition=item.condition
            )
        # otherwise group prev item with new
        else:
            # TODO: update indexes of all following comments in new_seq.ca
            prev_item = prev_item.with_conditional_block(
                data=group_conditional_blocks(item.data),
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


def _group_map_conditional_blocks(mapping: ConditionalMap) -> ConditionalMap:
    """Groups ConditionalBlock key-values into ConditionalGroup objects"""
    if len(mapping) == 0:
        return mapping

    new_map = ConditionalMap()
    # preserve original comment attributes
    mapping.copy_attributes(new_map)
    prev_item = None

    for (key, value) in mapping.items():
        if not isinstance(value, ConditionalBlock):
            if isinstance(value, ConditionalMap):
                value = _group_map_conditional_blocks(value)
            elif isinstance(value, ConditionalSeq):
                value = _group_seq_conditional_blocks(value)
            new_item = (key, value)
        elif (
            not prev_item
            or not isinstance(prev_item[1], ConditionalGroup)
            or value.typ is ConditionalBlockType.if_
        ):
            new_item = (
                key,
                ConditionalGroup(
                    body=group_conditional_blocks(value.data), condition=value.condition
                ),
            )
        # otherwise group prev item with new
        else:
            # remove key of prev item from the mapping
            prev_item = (
                key,
                prev_item[1].with_conditional_block(
                    data=group_conditional_blocks(value.data),
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
