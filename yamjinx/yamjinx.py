import re
from functools import partial
from typing import Optional

from ruamel.yaml import YAML, RoundTripConstructor, RoundTripRepresenter

from yamjinx.constants import (
    DEDUPLICATOR,
    DEFAULT_MAPPING_INDENT,
    DEFAULT_OFFSET_INDENT,
    DEFAULT_SEQUENCE_INDENT,
    YAML_MAP_TAG,
    YAML_SEQ_TAG,
)
from yamjinx.containers import (
    ConditionalNode,
    IndentConfig,
    ToggledData,
    ToggledMap,
    ToggledSeq,
)
from yamjinx.loader import translate_config_flags, validate_content
from yamjinx.loader.grouper import group_toggled_data
from yamjinx.representer import (
    translate_conditional_map_to_yaml,
    translate_conditional_seq_to_yaml,
)


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
        yaml.constructor.add_custom_constructor(YAML_MAP_TAG, _construct_map)
        yaml.constructor.add_custom_constructor(YAML_SEQ_TAG, _construct_seq)
        # add constructor for conditional structures, toggle information is parsed out
        # from the tag and saved as an attribute of ToggledMap object
        yaml.register_class(ConditionalNode)

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


def _construct_map(self, node):
    """Default constructor of map that instantiates custom
    ToggledMap object instead of CommentedMap"""
    data = ToggledMap()

    yield data
    self.construct_mapping(node, data, deep=True)
    self.set_collection_style(data, node)


def _construct_seq(self, node):
    """Default constructor of seq that instantiates custom
    ToggledSeq object instead of CommentedSeq"""
    data = ToggledSeq()

    yield data
    data.extend(self.construct_rt_sequence(node, data))
    self.set_collection_style(data, node)
