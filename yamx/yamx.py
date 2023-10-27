import re
from functools import partial
from typing import Optional

from ruamel.yaml import YAML, RoundTripConstructor, RoundTripRepresenter

from yamx.constants import (
    CONDITIONAL_TAG,
    DEDUPLICATOR,
    DEDUPLICATOR_UPD,
    DEFAULT_MAPPING_INDENT,
    DEFAULT_OFFSET_INDENT,
    DEFAULT_SEQUENCE_INDENT,
    YAML_MAP_TAG,
    YAML_SEQ_TAG,
)
from yamx.containers import (
    ConditionalBlock,
    ConditionalData,
    ConditionalMap,
    ConditionalSeq,
    IndentConfig,
)
from yamx.loader import translate_config_flags, validate_content
from yamx.loader.grouper import group_conditional_blocks
from yamx.representer import (
    translate_conditional_map_to_yaml,
    translate_conditional_seq_to_yaml,
)


class ConditionalRoundTripConstructor(RoundTripConstructor):
    def __init__(self, *args, **kwargs):
        self.yaml_constructors = self.__class__.yaml_constructors.copy()
        self.yaml_multi_constructors = self.__class__.yaml_multi_constructors.copy()
        super().__init__(*args, **kwargs)

    def add_custom_constructor(self, tag, constructor):
        self.yaml_constructors[tag] = constructor

    def add_custom_multi_constructor(self, tag, constructor):
        self.yaml_multi_constructors[tag] = constructor


class ConditionalRoundTripRepresenter(RoundTripRepresenter):
    def __init__(self, *args, **kwargs):
        self.yaml_representers = self.__class__.yaml_representers.copy()
        super().__init__(*args, **kwargs)

    def add_custom_representer(self, tag, representer):
        self.yaml_representers[tag] = representer


class YAMX:
    """Wrapper around ruamel loader that supports conditional functionality"""

    def __init__(self, yaml: Optional[YAML] = None, sort_keys: bool = True):
        """Initialize instance with custom YAML constructors and representers"""
        self.sort_keys = sort_keys

        if yaml is None:
            yaml = YAML(typ=["rt", "string"])
        else:
            assert isinstance(yaml, YAML), "Ruamel yaml loader/dumper is required"
            assert "rt" in yaml.typ, "RoundTripLoader/RoundTripDumper is required"

        yaml.Constructor = ConditionalRoundTripConstructor
        yaml.Representer = ConditionalRoundTripRepresenter
        # replace default constructor of map and seq - we need to have custom object for
        # each container to allow for condition modification
        yaml.constructor.add_custom_constructor(YAML_MAP_TAG, _construct_map)
        yaml.constructor.add_custom_constructor(YAML_SEQ_TAG, _construct_seq)
        # add constructor for conditional structures, condition information is parsed out
        # from the structure and saved as an attribute of ConditionalMap object
        # TODO: investigate why class register has flaky behaviour
        # yaml.register_class(ConditionalBlock)
        yaml.constructor.add_custom_constructor(
            CONDITIONAL_TAG, ConditionalBlock.from_yaml
        )

        self.yaml = yaml

        # setup custom representer for ConditionalMap and ConditionalSeq objects
        # and default indentation settings
        self.indent()

    def indent(
        self,
        mapping: int = DEFAULT_MAPPING_INDENT,
        sequence: int = DEFAULT_SEQUENCE_INDENT,
        offset: int = DEFAULT_OFFSET_INDENT,
    ) -> None:
        """Set indentation settings for mapping/sequence blocks"""
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
            ConditionalMap,
            partial(
                translate_conditional_map_to_yaml,
                sort_keys=self.sort_keys,
                indent_cfg=self.indent_cfg,
            ),
        )
        self.yaml.representer.add_custom_representer(
            ConditionalSeq,
            partial(
                translate_conditional_seq_to_yaml,
                sort_keys=self.sort_keys,
                indent_cfg=self.indent_cfg,
            ),
        )

    def load(self, stream) -> ConditionalData:
        data = stream.read()
        return self.load_from_string(data)

    def load_from_string(self, data: str) -> ConditionalData:
        validate_content(data)
        conf = translate_config_flags(data)
        data = self.yaml.load(conf)
        grouped_data = group_conditional_blocks(data)
        return ConditionalData(grouped_data)

    def dump(self, data: ConditionalData, stream) -> None:
        self.yaml.dump(
            data._data, stream, transform=self._remove_field_names_deduplicator
        )

    def dump_to_string(self, data: ConditionalData, **kwargs) -> str:
        raw_data = self.yaml.dump_to_string(data._data, **kwargs)
        return self._remove_field_names_deduplicator(raw_data)

    @staticmethod
    def _remove_field_names_deduplicator(s: str) -> str:
        """Removes all occurances of key suffixes used to deduplicated keys"""
        return re.sub(rf"({DEDUPLICATOR}|{DEDUPLICATOR_UPD})\d+", "", s)


def _construct_map(self, node):
    """Default constructor of map that instantiates custom
    ConditionalMap object instead of CommentedMap"""
    data = ConditionalMap()

    yield data
    self.construct_mapping(node, data, deep=True)
    self.set_collection_style(data, node)


def _construct_seq(self, node):
    """Default constructor of seq that instantiates custom
    ConditionalSeq object instead of CommentedSeq"""
    data = ConditionalSeq()

    yield data
    data.extend(self.construct_rt_sequence(node, data))
    self.set_collection_style(data, node)
