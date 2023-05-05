from attr import frozen


@frozen
class IndentConfig:
    mapping: int
    sequence: int
    offset: int
