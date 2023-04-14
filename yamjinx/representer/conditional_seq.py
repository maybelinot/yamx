from ruamel.yaml.nodes import SequenceNode

from yamjinx.containers.data import ToggledMap
from yamjinx.containers.settings import IndentConfig
from yamjinx.representer.common import translate_conditional_seq_to_commented_seq


def translate_conditional_seq_to_yaml(
    representer, data: ToggledMap, sort_keys: bool, indent_cfg: IndentConfig
) -> SequenceNode:
    cs = translate_conditional_seq_to_commented_seq(
        data=data,
        sort_keys=sort_keys,
        indent_cfg=indent_cfg,
        indent=0,
    )
    return representer.represent_sequence(data.tag.value, cs)
