import re
from functools import partial
from typing import Any, List, Mapping, Optional, Set, Tuple

from attr import frozen
from immutables import Map
from ruamel.yaml import YAML, RoundTripConstructor, RoundTripRepresenter

from yamjinx.constants import (
    DEDUPLICATOR,
    DEFAULT_MAPPING_INDENT,
    DEFAULT_OFFSET_INDENT,
    DEFAULT_SEQUENCE_INDENT,
    TOGGLE_SEP,
    TOGGLE_TAG_PREFIX,
    TOGGLE_VALUE_SETTER,
    TYPE_SEP,
    YAML_MAP_TAG,
    YAML_SEQ_TAG,
    ToggledBlockType,
)
from yamjinx.containers.data import ToggledMap, ToggledSeq
from yamjinx.containers.settings import IndentConfig
from yamjinx.extra import extract_toggles
from yamjinx.loader import translate_config_flags, validate_content
from yamjinx.loader.grouper import group_toggled_data
from yamjinx.representer import (
    translate_conditional_map_to_yaml,
    translate_conditional_seq_to_yaml,
)

# TODO: logic agnostic condition processing


@frozen
class ToggledData:
    """Wrapper for loaded data"""

    _data: Any

    @property
    def toggles(self) -> Set[str]:
        return extract_toggles(self._data)


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
                translate_conditional_map_to_yaml,
                sort_keys=self.sort_keys,
                indent_cfg=self.indent_cfg,
            ),
        )
        self.yaml.representer.add_custom_representer(
            ToggledSeq,
            partial(
                translate_conditional_seq_to_yaml,
                sort_keys=self.sort_keys,
                indent_cfg=self.indent_cfg,
            ),
        )

    def load(self, stream) -> ToggledData:
        data = stream.read()
        validate_content(data)
        conf = translate_config_flags(data)
        data = self.yaml.load(conf)
        grouped_data = group_toggled_data(data)
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
