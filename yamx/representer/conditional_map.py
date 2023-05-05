from ruamel.yaml.nodes import MappingNode

from yamx.containers.data import ConditionalMap
from yamx.containers.settings import IndentConfig
from yamx.representer.common import translate_conditional_map_to_commented_map


def translate_conditional_map_to_yaml(
    representer, data: ConditionalMap, sort_keys: bool, indent_cfg: IndentConfig
) -> MappingNode:
    # yield from representer.represent_mapping(None, data)
    cm = translate_conditional_map_to_commented_map(
        data=data, sort_keys=sort_keys, indent_cfg=indent_cfg, indent=0
    )
    return representer.represent_mapping(data.tag.value, cm)
