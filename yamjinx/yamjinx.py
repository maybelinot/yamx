import re
from collections import OrderedDict
from functools import partial, reduce
from typing import Any, Final, List, Mapping, Optional, Set, Tuple, Union

from attr import evolve, frozen
from immutables import Map
from ruamel.yaml import YAML, RoundTripConstructor, RoundTripRepresenter
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import CommentMark
from ruamel.yaml.nodes import MappingNode, SequenceNode
from ruamel.yaml.tokens import CommentToken

from yamjinx.constants import ToggledBlockType
from yamjinx.loader import translate_config_flags, validate_content

# TODO: logic agnostic condition processing
# TODO: interface to ST
yaml = YAML()

# indentetion defaults
DEFAULT_MAPPING_INDENT: Final[int] = 2
DEFAULT_SEQUENCE_INDENT: Final[int] = 2
DEFAULT_OFFSET_INDENT: Final[int] = 0
# yaml tags
YAML_MAP_TAG: Final[str] = "tag:yaml.org,2002:map"
YAML_SEQ_TAG: Final[str] = "tag:yaml.org,2002:seq"
# conditional comment templates
IF_TEMPLATE: Final[str] = '{{% if defines.get("{}") %}}'
ELIF_TEMPLATE: Final[str] = '{{% elif defines.get("{}") %}}'
IF_NOT_TEMPLATE: Final[str] = '{{% if not defines.get("{}") %}}'
ELIF_NOT_TEMPLATE: Final[str] = '{{% elif not defines.get("{}") %}}'
ELSE_COMMENT: Final[str] = "{% else %}"
ENDIF_COMMENT: Final[str] = "{% endif %}"

# toggled structure key constants
TOGGLE_KEY_PREFIX: Final[str] = "__toggled__"
UNIQUE_TOGGLE_CNT: int = 0
# toggled structure tag constants
TOGGLE_TAG_PREFIX: Final[str] = "!toggled_"
TYPE_SEP: Final[str] = "@"
TOGGLE_SEP: Final[str] = "&"
TOGGLE_VALUE_SETTER: Final[str] = "="
# toggled key deduplication
DEDUPLICATOR: Final[str] = "__deduplicator__"
UNIQUE_CNT: int = 0
CONSTRUCTOR_CNT: int = 0


@frozen
class ToggledData:
    """Wrapper for loaded data"""

    _data: Any

    @property
    def toggles(self) -> Set[str]:
        if isinstance(self._data, (ToggledMap, ToggledSeq)):
            return self._data.toggles
        return set()


class ToggledRoundTripConstructor(RoundTripConstructor):
    def __init__(self, *args, **kwargs):
        self.yaml_constructors = self.__class__.yaml_constructors.copy()
        self.yaml_multi_constructors = self.__class__.yaml_multi_constructors.copy()
        super().__init__(*args, **kwargs)

    def add_custom_constructor(self, tag, constructor):
        self.yaml_constructors[tag] = constructor

    def add_custom_multi_constructor(self, tag, constructor):
        self.yaml_multi_constructors[tag] = constructor


class ToggledRoundTripRepresenter(RoundTripRepresenter):
    def __init__(self, *args, **kwargs):
        self.yaml_representers = self.__class__.yaml_representers.copy()
        super().__init__(*args, **kwargs)

    def add_custom_representer(self, tag, representer):
        self.yaml_representers[tag] = representer


@frozen
class IndentConfig:
    mapping: int
    sequence: int
    offset: int


class YAMJinX:
    """Wrapper around ruamel loader that supports toggled functionality"""

    def __init__(self, yaml: Optional[YAML] = None, sort_keys: bool = True):
        self.sort_keys = sort_keys

        if yaml is None:
            yaml = YAML(typ=["rt", "string"])
        else:
            assert isinstance(yaml, YAML), "Ruamel yaml loader/dumper is required"
            assert "rt" in yaml.typ, "RoundTripLoader/RoundTripDumper is required"

        yaml.Constructor = ToggledRoundTripConstructor
        yaml.Representer = ToggledRoundTripRepresenter

        # replace default constructor of map and seq - we need to have custom object for
        # each container to allow for toggled modification
        yaml.constructor.add_custom_constructor(YAML_MAP_TAG, construct_map)
        yaml.constructor.add_custom_constructor(YAML_SEQ_TAG, construct_seq)
        # add multi constructors for all toggled tags, toggle information is parsed out
        # from the tag and saved as an attribute of ToggledMap object
        yaml.constructor.add_custom_multi_constructor(
            TOGGLE_TAG_PREFIX, construct_toggled_map
        )

        self.yaml = yaml

        # setup custom representer for ToggledMap and ToggledSeq objects
        # and default indentation settings
        self.indent()

    def indent(
        self,
        mapping: int = DEFAULT_MAPPING_INDENT,
        sequence: int = DEFAULT_SEQUENCE_INDENT,
        offset: int = DEFAULT_OFFSET_INDENT,
    ) -> None:
        indent_cfg = IndentConfig(
            mapping=mapping,
            sequence=sequence,
            offset=offset,
        )
        self.yaml.indent(
            mapping=indent_cfg.mapping,
            sequence=indent_cfg.sequence,
            offset=indent_cfg.offset,
        )
        self.indent_cfg = indent_cfg
        self._set_custom_representers()

    def _set_custom_representers(self) -> None:
        self.yaml.representer.add_custom_representer(
            ToggledMap,
            partial(
                ToggledMap.to_yaml, sort_keys=self.sort_keys, indent_cfg=self.indent_cfg
            ),
        )
        self.yaml.representer.add_custom_representer(
            ToggledSeq,
            partial(
                ToggledSeq.to_yaml, sort_keys=self.sort_keys, indent_cfg=self.indent_cfg
            ),
        )

    def load(self, stream) -> ToggledData:
        data = stream.read()
        validate_content(data)
        conf = translate_config_flags(data)
        data = self.yaml.load(conf)
        grouped_data = _group_toggled_data(data)
        return ToggledData(grouped_data)

    def dump(self, data: ToggledData, stream) -> None:
        self.yaml.dump(
            data._data, stream, transform=self._remove_field_names_deduplicator
        )

    def dump_to_string(self, data, **kwargs) -> str:
        raw_data = self.yaml.dump_to_string(data._data, **kwargs)
        return self._remove_field_names_deduplicator(raw_data)

    @staticmethod
    def _remove_field_names_deduplicator(s: str) -> str:
        """Removes all occurances of key suffixes used to deduplicated keys"""
        return re.sub(rf"{DEDUPLICATOR}\d+", "", s)


def _extract_toggle(toggles: Set[str], v: Any) -> Set[str]:
    if isinstance(v, (ToggledMap, ToggledSeq, ToggledGroup)):
        return toggles | v.toggles
    return toggles


class ToggledMap(CommentedMap):
    def __init__(
        self,
        typ: Optional[ToggledBlockType] = None,
        toggles: Optional[Mapping[str, bool]] = None,
    ):
        super().__init__()
        self.yaml_set_tag("tag:yaml.org,2002:map")
        self._typ = typ
        self._toggles = toggles or Map()

    @property
    def toggles(self) -> Set[str]:
        return reduce(_extract_toggle, self.values(), set(self._toggles))

    # alternative way to register representer (not needed when @yaml.register_class is used)
    # yaml.representer.add_representer(ToggledMap, ToggledMap.to_yaml)
    @classmethod
    def to_yaml(
        cls, representer, data: "ToggledMap", sort_keys: bool, indent_cfg: IndentConfig
    ) -> MappingNode:
        # yield from representer.represent_mapping(None, data)
        cm = data._translate_to_commented_map(
            sort_keys=sort_keys, indent_cfg=indent_cfg, indent=0
        )
        return representer.represent_mapping(data.tag.value, cm)

    # TODO: move outside of ToggledMap container
    def _translate_to_commented_map(
        self,
        sort_keys: bool,
        indent_cfg: IndentConfig,
        indent: int,
    ) -> CommentedMap:
        """NOTE: rendering of comments is happening inside->out
        first renders inner-most nested structure
        """

        if len(self) == 0:
            # TODO: preserve comments
            return CommentedMap()

        # storing all items
        # TODO: move sorting outside of translation
        if sort_keys:
            sorted_data = OrderedDict(
                sorted(
                    self.items(),
                    key=lambda i: i[1]
                    if isinstance(i[1], ToggledGroup)
                    else CmpValue(i[0]),
                )
            )
            data = ToggledMap()
            data.update(sorted_data)
            self.copy_attributes(data)
        else:
            data = self

        cm = _render_map_comments(
            data=data,
            indent=indent,
            indent_cfg=indent_cfg,
            sort_keys=sort_keys,
        )

        return cm


class ToggledSeq(CommentedSeq):
    def __init__(self) -> None:
        self.yaml_set_tag("tag:yaml.org,2002:seq")
        super().__init__()

    @property
    def toggles(self) -> Set[str]:
        return reduce(_extract_toggle, self, set())

    # alternative way to register representer (not needed when @yaml.register_class is used)
    # yaml.representer.add_representer(ToggledSeq, ToggledSeq.to_yaml)
    @classmethod
    def to_yaml(
        cls, representer, data: "ToggledSeq", sort_keys: bool, indent_cfg: IndentConfig
    ) -> SequenceNode:
        cs = data._translate_to_commented_seq(
            sort_keys=sort_keys,
            indent_cfg=indent_cfg,
            indent=0,
        )
        return representer.represent_sequence(data.tag.value, cs)

    def _translate_to_commented_seq(
        self, sort_keys: bool, indent_cfg: IndentConfig, indent: int
    ) -> CommentedSeq:
        if not len(self):
            return CommentedSeq()

        # adjusting extra indentation caused by artificially created structures
        cs = _render_seq_comments(
            data=self, indent=indent, indent_cfg=indent_cfg, sort_keys=sort_keys
        )

        return cs


@frozen
class CmpValue:
    value: Any

    def __lt__(self, other) -> bool:
        if isinstance(other, ToggledGroup):
            return True
        else:
            return self.value < other.value


@frozen
class ToggledGroup:
    # TODO: support scalars
    body: Union[ToggledMap, ToggledSeq]
    toggles_: Mapping[str, bool]
    # elif_bodies is None to identify elif nodes that have only body filled
    elif_bodies: Optional[Tuple[Union[ToggledMap, ToggledSeq], ...]] = tuple()
    else_body: Optional[Union[ToggledMap, ToggledSeq]] = None

    def __lt__(self, other) -> bool:
        # compare by toggle names
        if isinstance(other, ToggledGroup):
            return "".join(sorted(self.toggles)) < "".join(sorted(other.toggles))
        else:
            return False

    @property
    def toggles(self) -> Set[str]:
        toggles = set(self.toggles_)
        if isinstance(self.body, (ToggledMap, ToggledSeq)):
            toggles |= self.body.toggles
        if isinstance(self.else_body, (ToggledMap, ToggledSeq)):
            toggles |= self.else_body.toggles

        if self.elif_bodies is None:
            return toggles

        return reduce(_extract_toggle, self.elif_bodies, toggles)

    @classmethod
    def from_toggle_group_and_item(
        cls,
        toggled_group: "ToggledGroup",
        item: Union[ToggledMap, ToggledSeq],
        typ: ToggledBlockType,
        toggles: Mapping[str, bool],
    ) -> "ToggledGroup":
        if typ is ToggledBlockType.elif_:
            # TODO: validate toggle names and values uniqueness
            assert isinstance(toggled_group.elif_bodies, tuple)
            elif_groups = toggled_group.elif_bodies + (
                cls(body=item, toggles_=toggles, elif_bodies=None),
            )
            return evolve(toggled_group, elif_bodies=elif_groups)
        elif typ is ToggledBlockType.else_:
            assert (
                toggled_group.else_body is None
            ), f"Cannot set else_body to {toggled_group}, else_body is not empty."
            return evolve(toggled_group, else_body=item)
        else:
            raise ValueError(f"Unexpected toggled element of type {typ}")


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
    toggled_kwargs = {"indent": indent, "indent_cfg": indent_cfg, **kwargs}
    for item in data.items():
        if not isinstance(item[1], ToggledGroup):
            key, value = item
            # translate inner Toggled objects first
            if isinstance(value, ToggledMap):
                # add extra indentation for inner map structures
                value = value._translate_to_commented_map(
                    indent=indent + indent_cfg.mapping,
                    indent_cfg=indent_cfg,
                    **kwargs,
                )
            elif isinstance(value, ToggledSeq):
                # don't increase indent for sequence within map, as comments
                # are rendered on the same level
                value = value._translate_to_commented_seq(
                    indent=indent, indent_cfg=indent_cfg, **kwargs
                )
            cm[key] = value
            continue
        (_, toggled_group) = item
        ((toggle_key, toggle_value),) = toggled_group.toggles_.items()

        if toggle_value:
            if_comment = IF_TEMPLATE.format(toggle_key)
        else:
            if_comment = IF_NOT_TEMPLATE.format(toggle_key)

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
            ((toggle_key, toggle_value),) = elif_body.toggles_.items()
            # select template based on toggle value
            if toggle_value:
                before_comment = ELIF_TEMPLATE.format(toggle_key)
            else:
                before_comment = ELIF_NOT_TEMPLATE.format(toggle_key)

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
            resolved_data = _resolve_inner_toggle_groups(body=data, **toggled_kwargs)
            # render comment on original CommentedSeq and CommentedMap objects
            _render_toggle_data_map(
                cm,
                toggle_data=resolved_data,
                before=before,
                after=after,
                indent=indent,
                sort_keys=kwargs["sort_keys"],
            )

    return cm


def _resolve_inner_toggle_groups(
    body: Union[ToggledMap, ToggledSeq], **kwargs
) -> Union[CommentedMap, CommentedSeq]:
    """Render all toggle groups in the structure"""

    if isinstance(body, ToggledMap):
        return body._translate_to_commented_map(**kwargs)

    return body._translate_to_commented_seq(**kwargs)


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

    toggled_kwargs = {"indent": indent, "indent_cfg": indent_cfg, **kwargs}
    for item in data:
        if not isinstance(item, ToggledGroup):
            # TODO: propagate original comments
            if isinstance(item, ToggledMap):
                # add extra indentation for inner map structures
                item = item._translate_to_commented_map(
                    indent=indent + indent_cfg.mapping,
                    indent_cfg=indent_cfg,
                    **kwargs,
                )
            elif isinstance(item, ToggledSeq):
                # add extra indentation for inner seq structures
                item = item._translate_to_commented_seq(
                    indent=indent + indent_cfg.sequence,
                    indent_cfg=indent_cfg,
                    **kwargs,
                )
            cs.append(item)
            continue

        ((toggle_key, toggle_value),) = item.toggles_.items()
        if toggle_value:
            if_comment = IF_TEMPLATE.format(toggle_key)
        else:
            if_comment = IF_NOT_TEMPLATE.format(toggle_key)

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
            ((toggle_key, toggle_value),) = elif_body.toggles_.items()

            # select comment template to use based on toggle value
            if toggle_value:
                before_comment = ELIF_TEMPLATE.format(toggle_key)
            else:
                before_comment = ELIF_NOT_TEMPLATE.format(toggle_key)

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
            resolved_data = _resolve_inner_toggle_groups(body=data, **toggled_kwargs)
            _render_toggle_data_seq(
                cs,
                toggle_data=resolved_data,
                before=before,
                after=after,
                # adding extra indent based on the offset of seq items
                indent=indent + indent_cfg.offset,
            )

    return cs


def _group_toggled_data(data: Any) -> Any:
    if isinstance(data, ToggledMap):
        return _parse_toggled_map_data(data)
    elif isinstance(data, ToggledSeq):
        return _parse_toggled_seq_data(data)

    return data


def _parse_toggled_seq_data(seq: ToggledSeq) -> ToggledSeq:
    """Parses toggled key-values into ToggledGroup objects

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
        if (
            not isinstance(item, ToggledMap)
            or len(item) == 0
            or not (key := next(iter(item))).startswith(TOGGLE_KEY_PREFIX)
            # if list item is ToggledMap, but it's value is not a list
            # then we are dealing with list item that represents toggled map
            or not isinstance(item[key], list)
        ):
            if isinstance(item, ToggledMap):
                item = _parse_toggled_map_data(item)
            elif isinstance(item, ToggledSeq):
                item = _parse_toggled_seq_data(item)
            new_item = item
        elif (
            not isinstance(prev_item, ToggledGroup) or item._typ is ToggledBlockType.if_
        ):
            value = next(iter(item.values()))
            new_item = ToggledGroup(
                body=_group_toggled_data(value), toggles_=item._toggles
            )
        # otherwise group prev item with new
        else:
            # TODO: update indexes of all following comments in new_seq.ca
            value = next(iter(item.values()))
            prev_item = ToggledGroup.from_toggle_group_and_item(
                toggled_group=prev_item,
                item=_group_toggled_data(value),
                typ=item._typ,
                toggles=item._toggles,
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
    """Parses toggled key-values into ToggledGroup objects"""
    if len(mapping) == 0:
        return mapping

    new_map = ToggledMap()
    # preserve original comment attributes
    mapping.copy_attributes(new_map)
    prev_item = None

    for (key, value) in mapping.items():
        if not key.startswith(TOGGLE_KEY_PREFIX):
            if isinstance(value, ToggledMap):
                value = _parse_toggled_map_data(value)
            elif isinstance(value, ToggledSeq):
                value = _parse_toggled_seq_data(value)
            new_item = (key, value)
        elif (
            not prev_item
            or not isinstance(prev_item[1], ToggledGroup)
            or value._typ is ToggledBlockType.if_
        ):
            new_item = (
                key,
                ToggledGroup(body=_group_toggled_data(value), toggles_=value._toggles),
            )
        # otherwise group prev item with new
        else:
            # remove key of prev item from the mapping
            prev_item = (
                key,
                ToggledGroup.from_toggle_group_and_item(
                    toggled_group=prev_item[1],
                    item=_group_toggled_data(value),
                    typ=value._typ,
                    toggles=value._toggles,
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


def _render_toggle_data_map(
    cm: CommentedMap,
    toggle_data: ToggledMap,
    before: Optional[str],
    after: Optional[str],
    indent: int,
    sort_keys: bool,
) -> CommentedMap:
    """
    CommentedMap object has following comment attributes:

    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@    cm.ca.comment    @@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

    cm.ca.comment: [comment1, [comment2, ...], [comment3, ...]] = None
        Denote 3 types of comments:
        1. single comment placed before first key-value and `-` if it's an item of commentedSeq,
           new line is added at the end if missing.
            type: Optional[CommentToken]
        2. multi comment placed before first key-value and after `-` if it's an item of commentedSeq
            type: Optional[List[CommentToken]]]
        3. multi comment placed after all key-values of the mapping
            type: Optional[List[CommentToken]]]

        Let's see how it works on the example:

        > cm = CommentedMap({"first":1, "second":2})
        > mark = CommentMark(0) # mark represents indentation
        > cm.ca.comment = [
            CommentToken("# COMMENT1", mark),
            [CommentToken("# COMMENT2\n", mark)],
            [CommentToken("# COMMENT3\n", mark)]
        ]

    NOTE: Rendering of the comment varies based on parent object annotation.
    The reason is that during represenation `comment` attribute is propagated
    to relevant `items` attribute of the parent object (see `items` comment attribute)

    ====== CommentedSeq parent object =======
        > yaml.dump_to_string(CommentedSeq(cm))

        # COMMENT2
        - # COMMENT1
        first: 1
        second: 2
        # COMMENT3


    ====== CommentedMap parent object =======
        > yaml.dump_to_string(CommentedMap(map=cm))

        map: # COMMENT1
        # COMMENT2
        first: 1
        second: 2
        # COMMENT3


    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@     cm.ca.items     @@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

    cm.ca.items: Dict[int, [comment1, [comment2, ...], comment3, [comment4,...]]] = {}
        Denotes 4 types of comments attached to particular element of a key-value
        1. single comment (new line is added at the end if missing)
            position: right after key, but before `:`
            type: Optional[CommentToken]
        2. multi comment placed before key
            type: Optional[List[CommentToken]]]
        3. single comment (new line is added at the end if missing)
            position: right after `:` if value is of type map or seq, otherwise after value
            type: Optional[CommentToken]
        4. multi comment (ignored if value is a scalar)
            position: before value
            type: Optional[List[CommentToken]]]

        Key of ca.items dict is a key of key-value pair in a mapping


        let's see how it works on following example:
        > cm = CommentedMap({"first": 1})
        > cm.ca.items["first"] = [
            CommentToken("# COMMENT1", mark),
            [CommentToken("# COMMENT2\n", mark)],
            CommentToken("# COMMENT3", mark),
            [CommentToken("# COMMENT4\n", mark)],
        ]
        > outer_map = CommentedMap(outer=cm)
        > print(yaml.dump_to_string(outer_map))

        outer:
        # COMMENT2
        first # COMMENT1
        : 1 # COMMENT3

    NOTE: items annotation of parent object can CONFLICT with `comment` (see above)
    annotation of a children:


    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@     cm.ca.end     @@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

    doesn't seem to have any specific usage for CommentedMap
    """
    global UNIQUE_CNT

    # TODO: return if empty
    if len(toggle_data) == 0:
        raise NotImplementedError

    # TODO: move sorting to different place
    if sort_keys:
        iter_data = enumerate(sorted(toggle_data.items(), key=lambda kv: kv[0]))
    else:
        iter_data = enumerate(toggle_data.items())

    for idx, (data_key, data_value) in iter_data:
        if data_key in cm:
            # TODO: log proper warning + handle deduplicated keys
            print(f"warning: Duplicate '{data_key}' key encountered")
        prev_data_key = data_key
        # to avoid keys duplication - adding unique suffix
        if DEDUPLICATOR not in data_key:
            # TODO: replace with hash of stable length
            data_key = f"{data_key}{DEDUPLICATOR}{UNIQUE_CNT}"
            UNIQUE_CNT += 1

        # move prev comment annotation to cm
        if prev_data_key in toggle_data.ca.items:
            cm.ca.items.update({data_key: toggle_data.ca.items[prev_data_key]})

        if idx == 0:
            first_data_key = data_key
        cm.update({data_key: data_value})

    last_data_key = data_key
    # when toggled block consist of multiple elements we need to
    # attach before and after comment to different items

    # first attaching before comment to the first added item
    if before is not None:
        _annotate_commented_map_scalar_item(
            commented_data=cm,
            data_key=first_data_key,
            before=before,
            after=None,
            indent=indent,
        )

    # now attaching after comment to the last added item
    if after is not None:
        if isinstance(cm[last_data_key], CommentedMap):
            # propagate after comment all the way to the outermost element of the structure
            _set_after_map_comment(cm=cm[last_data_key], after=after, indent=indent)
        elif isinstance(cm[last_data_key], CommentedSeq) and len(cm[last_data_key]):
            _annotate_commented_seq_commented_item(
                item=cm[last_data_key],
                before=None,
                after=after,
                indent=indent,
            )
        else:
            # otherwise value is a simple scalar - setting annotation on items attribute of a
            # parent object
            _annotate_commented_map_scalar_item(
                commented_data=cm,
                data_key=last_data_key,
                before=None,
                after=after,
                indent=indent,
            )


def _annotate_commented_map_scalar_item(
    commented_data: Union[CommentedMap, CommentedSeq],
    data_key: Union[str, int],
    before: Optional[str],
    after: Optional[str],
    indent: int,
) -> None:
    """Annotating simple scalar value
    Comment annotations are attached to parent object ca.items structure
    """
    # create comment tokens
    mark = CommentMark(indent)
    before_comment = before and CommentToken(f"# {before}\n", mark)
    # NOTE: comment is prefixed with new line as it is attached after value
    after_comment = after and CommentToken(f"\n{' '*indent}# {after}", mark)

    prev_ca = commented_data.ca.items.get(data_key)
    # item could be already annotated, let's extract the comments and merge them
    if prev_ca:
        # prepare after_comments
        if after_comment and prev_ca[2]:
            after_comments = _merge_comments(prev_ca[2], after_comment)
        elif after_comment:
            after_comments = after_comment
        else:
            after_comments = prev_ca[2]
        # prepare before_comments
        if before_comment is not None:
            before_comments = [before_comment, *(prev_ca[1] or [])]
        else:
            before_comments = prev_ca[1]

        new_ca = [
            None,
            before_comments,
            after_comments,
            None,
        ]
    else:
        new_ca = [None, before_comment and [before_comment], after_comment, None]

    commented_data.ca.items[data_key] = new_ca


def _set_after_map_comment(cm, after: str, indent: int) -> None:
    """Recursively propagates after comment to the last map item"""
    # in case CommentedMap is empty - attaching comment to cm.ca
    mark = CommentMark(indent)
    after_comment = CommentToken(f"\n{' '*indent}# {after}", mark)

    if len(cm) == 0:
        cm.ca.comment = [after_comment, []]
        return
    # otherwise, propagating deeper
    last_map_key = next(reversed(cm))
    if isinstance(cm[last_map_key], CommentedMap):
        _set_after_map_comment(cm[last_map_key], after, indent=indent)
    elif isinstance(cm[last_map_key], CommentedSeq) and len(cm[last_map_key]):
        _annotate_commented_seq_commented_item(
            item=cm[last_map_key],
            before=None,
            after=after,
            indent=indent,
        )
    else:
        try:
            cm.ca.items[last_map_key][2] = _merge_comments(
                cm.ca.items[last_map_key][2], after_comment
            )
        except KeyError:
            cm.ca.items[last_map_key] = [None, None, after_comment, None]


def _merge_comments(comment1: CommentToken, comment2: CommentToken) -> CommentToken:
    """Used to merge 2 comments into a single CommentToken object
    NOTE: only single-line comments are supported
    """
    assert comment1.value.startswith("\n")
    assert comment2.value.startswith("\n")

    indent = min(comment1.column, comment2.column)
    mark = CommentMark(indent)

    return CommentToken(
        f"{comment1.value}{comment2.value}",
        mark,
    )


def _render_toggle_data_seq(
    cs: CommentedSeq,
    toggle_data: CommentedSeq,
    before: Optional[str],
    after: Optional[str],
    indent: int,
) -> None:
    """
    CommentedSeq object has following comment attributes:

    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@    cs.ca.comment    @@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

    cs.ca.comment: [comment1, [comment2, ...], [comment3, ...]] = None
        Denote 3 types of comments:
        1. single comment placed right before `-` sign (new line is added at the end if missing)
            type: Optional[CommentToken]
        2. multi comment placed right after `-` sign
            type: Optional[List[CommentToken]]]
        3. multi comment placed after all elements of the sequence
            type: Optional[List[CommentToken]]]
            note: comment is placed only in case of non empty sequence

        Let's see how it works on the example:

        > cs = CommentedSeq([1,2])
        > mark = CommentMark(0) # mark represents indentation
        > cs.ca.comment = [
            CommentToken("# COMMENT1", mark),
            [CommentToken("# COMMENT2\n", mark)],
            [CommentToken("# COMMENT3\n", mark)]
        ]

    NOTE: Rendering of the comment varies based parent object annotation.
    The reason is that during represenation `comment` attribute is propagated
    to relevant `items` attribute of the parent object (see `items` comment attribute)

    ====== CommentedSeq parent object =======
        > yaml.dump_to_string(CommentedSeq(cs))

        # COMMENT2
        - # COMMENT1
            - 1
            - 2
        # COMMENT3


    ====== CommentedMap parent object =======
        > yaml.dump_to_string(CommentedMap(list=cs))

        list: # COMMENT1
        # COMMENT2
        - 1
        - 2
        # COMMENT3


    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@     cs.ca.items     @@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

    cs.ca.items: Dict[int, [comment1, [comment2, ...]]] = {}
        Denotes 2 types of comments attached to particular element of a sequence
        1. single comment placed after seq item value
            type: Optional[CommentToken]
        2. multi comment placed before `-` sign (new line is added at the end if missing)
            type: Optional[List[CommentToken]]]
        Key of ca.items dict is an index of an element in the list


        let's see how it works on the example:
        > cs = CommentedSeq([1])
        > cs.ca.items[0] = [
            CommentToken("# COMMENT1", mark),
            [CommentToken("# COMMENT2\n", mark)],
        ]
        > yaml.dump_to_string(CommentedSeq(cs))

        # COMMENT2
        - 1 # COMMENT1

    NOTE: items annotation of parent object can CONFLICT with `comment` (see above)
    and `end` (see below) annotations of a children:

    If parent object has defined `items` annotation for particular element - following applies:

    1. Any item annotation from a parent object make representer ignore 3rd comment of children
    cs.ca.comment annotation

        > cs = CommentedSeq([1,2])
        > mark = CommentMark(0) # mark represents indentation
        > cs.ca.comment = [
            CommentToken("# COMMENT1", mark),
            [CommentToken("# COMMENT2\n", mark)],
            [CommentToken("# COMMENT3\n", mark)]
        ]
        parent_cs = CommentedSeq([cs])
        parent_cs.items[0] = [None, None]
        > yaml.dump_to_string(parent_cs)

        # COMMENT2
        - # COMMENT1
            - 1

    2. Once commented structure is representer certain modifications are happening to
        annotated structure:
        * comment1 of cs.comment anntotation is propagated to comment1 annotation
            of parent_cs.items[0]
        * the same logic applies to comment2 of cs.comment and parent_cs.items[0] respectively
            NOTE: Propagation is only happening to parent structure, not to the children
            NOTE: Propagation doesn't happen if parent_cs.items[0] is not defined
            NOTE: If both comments of parent_cs and cs are defined when attepmt to represent
                    a structure ASSERTION error is raised


    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@     cs.ca.end     @@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

    doesn't seem to have any specific usage for CommentedSeq
    """

    first_item_pos = len(cs)
    last_item_pos = first_item_pos + len(toggle_data) - 1

    assert first_item_pos <= last_item_pos

    # NOTE: extend method will shift comment annotation of all comments with
    # ids higher than last element - we should extend first, annotate after
    cs.extend(toggle_data)
    # now we can extend cs.ca with annotation of newly added items
    # in order to do that we need to shift all indices by len of cs
    cs.ca.items.update(
        {first_item_pos + key: comment for key, comment in toggle_data.ca.items.items()}
    )
    # when toggled block consist of multiple elements we need to
    # attach before and after comment to different items

    # first attaching before comment to the first added item
    if before is not None:
        if isinstance(cs[first_item_pos], CommentedMap):
            _annotate_commented_map_scalar_item(
                commented_data=cs,
                data_key=first_item_pos,
                before=before,
                after=None,
                indent=indent,
            )
        elif isinstance(cs[first_item_pos], CommentedSeq):
            _annotate_commented_seq_commented_item(
                item=cs[first_item_pos],
                before=before,
                after=None,
                indent=indent,
            )
        else:
            # otherwise item is a simple scalar - setting annotation on items attribute of a
            # parent object
            _annotate_commented_seq_scalar_item(
                cs=cs,
                item_idx=first_item_pos,
                before=before,
                after=None,
                indent=indent,
            )

    # now attaching after comment to the last added item
    if after is not None:
        if isinstance(cs[last_item_pos], CommentedMap):
            _set_after_map_comment(cm=cs[last_item_pos], after=after, indent=indent)
        elif isinstance(cs[last_item_pos], CommentedSeq) and len(cs[last_item_pos]):

            _annotate_commented_seq_commented_item(
                item=cs[last_item_pos],
                before=None,
                after=after,
                indent=indent,
            )
        else:
            # otherwise item is a simple scalar - setting annotation on items attribute of a
            # parent object
            _annotate_commented_seq_scalar_item(
                cs=cs,
                item_idx=last_item_pos,
                before=None,
                after=after,
                indent=indent,
            )


def _annotate_commented_seq_commented_item(
    item: CommentedSeq, before: Optional[str], after: Optional[str], indent: int
) -> None:
    """Annotating commented values
    Comment annotations are attached to actual item object ca.comment structure
    """
    mark = CommentMark(indent)
    # create comment tokens
    before_comment = before and [CommentToken(f"# {before}\n", mark)]
    after_comment = after and [CommentToken(f"# {after}\n", mark)]

    # item could be already annotated, let's extract the comments and merge them
    if prev_ca := item.ca.comment:
        new_ca = [
            None,
            # merge comments into list if it's not None
            ((before_comment or []) + (prev_ca[1] or [])) or None,
            ((prev_ca[2] or []) + (after_comment or [])) or None,
        ]
    else:
        new_ca = [
            None,
            # put comments into list if it's not None
            before_comment,
            after_comment,
        ]
    item.ca.comment = new_ca


def _annotate_commented_seq_scalar_item(
    cs: CommentedSeq,
    item_idx: int,
    before: Optional[str],
    after: Optional[str],
    indent: int,
) -> None:
    """Annotating simple scalar value
    Comment annotations are attached to parent object ca.items structure
    """
    # create comment tokens
    mark = CommentMark(indent)
    before_comment = before and CommentToken(f"# {before}\n", mark)
    # NOTE: comment is prefixed with new line as it is attached after value
    after_comment = after and CommentToken(f"\n{' '*indent}# {after}", mark)

    prev_ca = cs.ca.items.get(item_idx)
    # item could be already annotated, let's extract the comments and merge them
    if prev_ca:
        # prepare after_comments
        if after_comment and prev_ca[0]:
            after_comments = _merge_comments(prev_ca[0], after_comment)
        elif after_comment:
            after_comments = after_comment
        else:
            after_comments = prev_ca[0]
        # prepare before_comments
        if before_comment is not None:
            before_comments = [before_comment, *(prev_ca[1] or [])]
        else:
            before_comments = prev_ca[1]

        new_ca = [
            after_comments,
            before_comments,
        ]
    else:
        new_ca = [after_comment, before_comment and [before_comment]]

    cs.ca.items[item_idx] = new_ca


def construct_map(self, node):
    """Default constructor of map that instantiates custom
    ToggledMap object instead of CommentedMap"""
    data = ToggledMap()
    data._yaml_set_line_col(node.start_mark.line, node.start_mark.column)
    data.yaml_set_tag(node.tag)
    yield data
    self.construct_mapping(node, data, deep=True)
    self.set_collection_style(data, node)


def construct_seq(self, node):
    """Default constructor of seq that instantiates custom
    ToggledSeq object instead of CommentedSeq"""
    data = ToggledSeq()
    data._yaml_set_line_col(node.start_mark.line, node.start_mark.column)
    yield data
    data.extend(self.construct_rt_sequence(node, data))
    self.set_collection_style(data, node)


def _extract_typ_and_toggles_from_tag(
    tag: str,
) -> Tuple[ToggledBlockType, Mapping[str, bool]]:
    """Extract type and toggle information from yaml tag

    Example input:
    "if@toggle1_name=True&toggle2_name=False"

    Example output:
    (
        ToggledBlockType.if_,
        Map(
            toggle1_name=True,
            toggle2_name=False,
        )
    )
    """

    def _split_toggle_key_value(s: str) -> List[str]:
        return s.split(TOGGLE_VALUE_SETTER)

    (typ, toggles) = tag.split(TYPE_SEP)
    typ = ToggledBlockType(typ)
    # else tag doesn't contain any toggles
    if typ is ToggledBlockType.else_:
        assert toggles == ""
        return (typ, Map())

    return (
        typ,
        Map(
            {
                key: value == "True"
                for key, value in map(
                    _split_toggle_key_value, toggles.split(TOGGLE_SEP)
                )
            }
        ),
    )


def construct_toggled_map(self, tag_suffix, node):
    """Default constructor of map that instantiates custom ToggledMap object with toggles info
    extracted from tag suffix instead of CommentedMap
    """
    if tag_suffix is None:
        raise Exception("Unexpected empty tag_suffix.")

    (typ, toggles) = _extract_typ_and_toggles_from_tag(tag_suffix)
    data = ToggledMap(typ, toggles)

    # replacing tag to mapping to avoid any custom tag info to be populated into the output
    data.yaml_set_tag(YAML_MAP_TAG)
    yield data

    self.construct_mapping(node, data, deep=True)
    self.set_collection_style(data, node)
