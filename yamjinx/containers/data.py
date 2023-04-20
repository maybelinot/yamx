from typing import Any, ClassVar, Optional, Tuple, Union

from attr import evolve, frozen
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from yamjinx.constants import (
    CONDITIONAL_TAG,
    YAML_MAP_TAG,
    YAML_SEQ_TAG,
    ToggledBlockType,
)


@frozen
class CmpValue:
    value: Any

    def __lt__(self, other) -> bool:
        if isinstance(other, ConditionalGroup):
            return True
        else:
            return self.value < other.value


class ToggledMap(CommentedMap):
    def __init__(
        self,
    ):
        super().__init__()
        self.yaml_set_tag(YAML_MAP_TAG)


class ToggledSeq(CommentedSeq):
    def __init__(self) -> None:
        self.yaml_set_tag(YAML_SEQ_TAG)
        super().__init__()


@frozen
class ConditionalNode:
    yaml_tag: ClassVar[str] = CONDITIONAL_TAG

    data: Any
    typ: ToggledBlockType
    condition: Optional[str]

    @classmethod
    def to_yaml(cls, _, __):
        raise NotImplementedError(f"{cls.__name__} should never be dumped to yaml.")

    @classmethod
    def from_yaml(cls, constructor, node):
        data = CommentedMap()
        constructor.construct_mapping(node, data, deep=True)
        data["typ"] = ToggledBlockType(data["typ"])

        return cls(**data)


@frozen
class ConditionalGroup:
    condition: Optional[str]
    # TODO: support scalars
    body: Union[ToggledMap, ToggledSeq]
    # elif_bodies is None to identify elif nodes that have only body filled
    elif_bodies: Optional[Tuple["ConditionalGroup", ...]] = tuple()
    else_body: Optional[Union[ToggledMap, ToggledSeq]] = None

    def __lt__(self, other) -> bool:
        # compare by toggle names
        if isinstance(other, ConditionalGroup):
            # we compare only "if" ConditionalGroup, not "else" (where condition can be empty)
            assert self.condition is not None and other.condition is not None
            return self.condition < other.condition
        else:
            return False

    def with_conditional_block(
        self,
        data: Union[ToggledMap, ToggledSeq],
        typ: ToggledBlockType,
        condition: Optional[str],
    ) -> "ConditionalGroup":
        """Extends conditional group with new elif/else conditional blocks"""
        if typ is ToggledBlockType.elif_:
            assert isinstance(self.elif_bodies, tuple)
            elif_groups = self.elif_bodies + (
                ConditionalGroup(body=data, condition=condition, elif_bodies=None),
            )
            return evolve(self, elif_bodies=elif_groups)
        elif typ is ToggledBlockType.else_:
            assert (
                self.else_body is None
            ), f"Cannot set else_body to {self}, else_body is not empty."
            return evolve(self, else_body=data)
        else:
            raise ValueError(f"Unexpected toggled element of type {typ}")
