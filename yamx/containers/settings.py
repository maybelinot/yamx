from dataclasses import dataclass


@dataclass(frozen=True)
class IndentConfig:
    mapping: int
    sequence: int
    offset: int
