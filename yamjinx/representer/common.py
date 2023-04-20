from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple, Union

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from yamjinx.constants import (
    ELIF_CONDITION_TEMPLATE,
    ELSE_COMMENT,
    ENDIF_COMMENT,
    IF_CONDITION_TEMPLATE,
)
from yamjinx.containers.data import CmpValue, ConditionalGroup, ToggledMap, ToggledSeq
from yamjinx.containers.settings import IndentConfig
from yamjinx.representer.rendering import render_toggle_data_map, render_toggle_data_seq


def translate_conditional_map_to_commented_map(
    data: ToggledMap,
    sort_keys: bool,
    indent_cfg: IndentConfig,
    indent: int,
) -> CommentedMap:
    """NOTE: rendering of comments is happening inside->out
    first renders inner-most nested structure
    """

    if len(data) == 0:
        # TODO: preserve comments
        return CommentedMap()

    # storing all items
    # TODO: move sorting outside of translation
    if sort_keys:
        sorted_data = OrderedDict(
            sorted(
                data.items(),
                key=lambda i: i[1]
                if isinstance(i[1], ConditionalGroup)
                else CmpValue(i[0]),
            )
        )
        new_data = ToggledMap()
        new_data.update(sorted_data)
        data.copy_attributes(data)
    else:
        new_data = data

    cm = _render_map_comments(
        data=new_data,
        indent=indent,
        indent_cfg=indent_cfg,
        sort_keys=sort_keys,
    )

    return cm


def _render_map_comments(
    data: ToggledMap, indent: int, indent_cfg: IndentConfig, **kwargs
) -> CommentedMap:
    """
    Converts ToggledMap structure into CommentedMap
    rendering all sequence comment

    kwargs contain parameters used to recursively render inner structures
    such as:
    :param sort_keys: {bool}
    """
    cm = CommentedMap()
    toggled_kwargs: Dict[str, Any] = {
        "indent": indent,
        "indent_cfg": indent_cfg,
        **kwargs,
    }
    for item in data.items():
        if not isinstance(item[1], ConditionalGroup):
            key, value = item
            # translate inner Toggled objects first
            if isinstance(value, ToggledMap):
                # add extra indentation for inner map structures
                value = translate_conditional_map_to_commented_map(
                    data=value,
                    indent=indent + indent_cfg.mapping,
                    indent_cfg=indent_cfg,
                    **kwargs,
                )
            elif isinstance(value, ToggledSeq):
                # don't increase indent for sequence within map, as comments
                # are rendered on the same level
                value = translate_conditional_seq_to_commented_seq(
                    data=value, indent=indent, indent_cfg=indent_cfg, **kwargs
                )
            cm[key] = value
            continue
        (_, toggled_group) = item

        if_comment = IF_CONDITION_TEMPLATE.format(toggled_group.condition)

        to_render: List[
            Tuple[Union[ToggledMap, ToggledSeq], Optional[str], Optional[str]]
        ] = []

        # in case we have only if body
        if toggled_group.else_body is None and not toggled_group.elif_bodies:
            # TODO: create nice wrapper for this structure of
            # tuple(data, comment_before, comment_after)
            to_render.append((toggled_group.body, if_comment, ENDIF_COMMENT))
        else:
            to_render.append((toggled_group.body, if_comment, None))

        # render elif blocks
        elif_bodies_count = len(toggled_group.elif_bodies)
        for idx, elif_body in enumerate(toggled_group.elif_bodies):
            before_comment = ELIF_CONDITION_TEMPLATE.format(elif_body.condition)
            # set after comment based if it's last elif block and
            # there is no else statement in the toggled group
            if (idx == elif_bodies_count - 1) and toggled_group.else_body is None:
                after_comment = ENDIF_COMMENT
            else:
                after_comment = None

            to_render.append((elif_body.body, before_comment, after_comment))

        if toggled_group.else_body:
            to_render.append((toggled_group.else_body, ELSE_COMMENT, ENDIF_COMMENT))

        # render all toggled group blocks
        for (data, before, after) in to_render:

            # resolve all inner structures first
            resolved_data = translate_conditional_map_to_commented_map(
                data=data, **toggled_kwargs
            )
            # render comment on original CommentedSeq and CommentedMap objects
            render_toggle_data_map(
                cm,
                toggle_data=resolved_data,
                before=before,
                after=after,
                indent=indent,
                sort_keys=kwargs["sort_keys"],
            )

    return cm


def translate_conditional_seq_to_commented_seq(
    data: ToggledSeq,
    sort_keys: bool,
    indent_cfg: IndentConfig,
    indent: int,
) -> CommentedMap:
    """NOTE: rendering of comments is happening inside->out
    first renders inner-most nested structure
    """

    if not len(data):
        return CommentedSeq()

    # adjusting extra indentation caused by artificially created structures
    cs = _render_seq_comments(
        data=data, indent=indent, indent_cfg=indent_cfg, sort_keys=sort_keys
    )

    return cs


def _render_seq_comments(
    data: ToggledSeq, indent: int, indent_cfg: IndentConfig, **kwargs
) -> CommentedSeq:
    """
    Converts ToggledSeq structure into CommentedSeq
    rendering all sequence comment

    kwargs contain parameters used to recursively render inner structures
    such as:
    :param sort_keys: {bool}
    """
    cs = CommentedSeq()

    toggled_kwargs: Dict[str, Any] = {
        "indent": indent,
        "indent_cfg": indent_cfg,
        **kwargs,
    }
    for item in data:
        if not isinstance(item, ConditionalGroup):
            # TODO: propagate original comments
            if isinstance(item, ToggledMap):
                # add extra indentation for inner map structures
                item = translate_conditional_map_to_commented_map(
                    data=item,
                    indent=indent + indent_cfg.mapping,
                    indent_cfg=indent_cfg,
                    **kwargs,
                )
            elif isinstance(item, ToggledSeq):
                # add extra indentation for inner seq structures
                item = translate_conditional_seq_to_commented_seq(
                    data=item,
                    indent=indent + indent_cfg.sequence,
                    indent_cfg=indent_cfg,
                    **kwargs,
                )
            cs.append(item)
            continue

        if_comment = IF_CONDITION_TEMPLATE.format(item.condition)

        to_render: List[
            Tuple[Union[ToggledMap, ToggledSeq], Optional[str], Optional[str]]
        ] = []
        # in case we have only if body
        if item.else_body is None and not item.elif_bodies:
            # TODO: create nice wrapper for this structure of
            # tuple(data, comment_before, comment_after)
            to_render.append((item.body, if_comment, ENDIF_COMMENT))
        else:
            to_render.append((item.body, if_comment, None))

        # render elif blocks
        assert item.elif_bodies is not None
        elif_bodies_count = len(item.elif_bodies)
        for idx, elif_body in enumerate(item.elif_bodies):
            before_comment = ELIF_CONDITION_TEMPLATE.format(elif_body.condition)
            # set after comment if it's last elif block and else block is
            # not present in the toggled group
            if (idx == elif_bodies_count - 1) and item.else_body is None:
                after_comment = ENDIF_COMMENT
            else:
                after_comment = None

            to_render.append((elif_body.body, before_comment, after_comment))

        # render else comment if exists
        if item.else_body:
            to_render.append((item.else_body, ELSE_COMMENT, ENDIF_COMMENT))

        # TODO: merge with map processing
        # render all toggled group blocks
        for (data, before, after) in to_render:
            # resolve all inner structures first
            resolved_data = translate_conditional_seq_to_commented_seq(
                data=data, **toggled_kwargs
            )
            render_toggle_data_seq(
                cs,
                toggle_data=resolved_data,
                before=before,
                after=after,
                # adding extra indent based on the offset of seq items
                indent=indent + indent_cfg.offset,
            )

    return cs
