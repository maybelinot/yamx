from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Final, Mapping

from immutables import Map
from jinja2 import Environment, nodes
from jinja2.compiler import CodeGenerator, EvalContext, Frame

from yamx.containers.data import Condition


def extract_condition(node: nodes.Test, env: Environment) -> Condition:
    generator = CustomCodeGenerator(env, None, None)
    eval_ctx = EvalContext(env, "")
    frame = Frame(eval_ctx)
    generator.visit(node, frame)
    return Condition(generator.stream.getvalue().strip())


class CustomCodeGenerator(CodeGenerator):
    """Generator used to stringify expressions you can find inside if node"""

    def write(self, x):
        self.stream.write(x)

    def visit_Name(self, node, frame):
        self.write(node.name)

    def visit_Const(self, node, frame):
        if isinstance(node.value, str):
            self.write('"{}"'.format(node.value))
        else:
            super().visit_Const(node, frame)

    def visit_Getattr(self, node, frame):
        self.visit(node.node, frame)

        self.write("." + node.attr)

    def visit_Getitem(self, node, frame):
        self.visit(node.node, frame)

        self.write("[")
        self.visit(node.arg, frame)
        self.write("]")

    def visit_Call(self, node, frame):
        self.visit(node.node, frame)
        self.write("(")
        for idx, arg in enumerate(node.args):
            self.visit(arg, frame)
            if idx != len(node.args) - 1:
                self.write(",")
        self.write(")")


def _make_binop(
    name: str, op: str
) -> Callable[["CodeGenerator", nodes.BinExpr, "Frame"], None]:
    def visitor(self: "CodeGenerator", node: nodes.BinExpr, frame: Frame) -> None:

        left_op = OPS_REGISTER.get(type(node.left).__name__, MAX_PREC_OP)

        if (
            OPS_REGISTER[name].precedence >= left_op.precedence
            and left_op.typ == OpType.binary
        ):
            self.write("(")
            self.visit(node.left, frame)
            self.write(")")
        else:
            self.visit(node.left, frame)

        self.write(f" {op} ")

        right_op = OPS_REGISTER.get(type(node.right).__name__, MAX_PREC_OP)
        if (
            OPS_REGISTER[name].precedence > right_op.precedence
            and right_op.typ == OpType.binary
        ):
            self.write("(")
            self.visit(node.right, frame)
            self.write(")")
        else:
            self.visit(node.right, frame)

    return visitor


def _make_unop(
    name: str,
    op: str,
) -> Callable[["CodeGenerator", nodes.UnaryExpr, "Frame"], None]:
    def visitor(self: "CodeGenerator", node: nodes.UnaryExpr, frame: Frame) -> None:
        inner_op = OPS_REGISTER.get(type(node.node).__name__, MIN_PREC_OP)
        if OPS_REGISTER[name].precedence >= inner_op.precedence:
            self.write(f"{op} ")
            self.visit(node.node, frame)
        else:
            self.write(f"{op}(")
            self.visit(node.node, frame)
            self.write(")")

    return visitor


class OpType(Enum):
    binary = auto()
    unary = auto()
    undefined = auto()


@dataclass(frozen=True)
class Op:
    name: str
    typ: OpType
    precedence: int


MAX_PREC_OP = Op("", OpType.undefined, 20)
MIN_PREC_OP = Op("", OpType.undefined, 0)

OPS_REGISTER: Final[Mapping[str, Op]] = Map(
    {
        "Pos": Op("+", OpType.unary, 1),
        "Neg": Op("-", OpType.unary, 1),
        "Add": Op("+", OpType.binary, 2),
        "Sub": Op("-", OpType.binary, 2),
        "Mul": Op("*", OpType.binary, 3),
        "Div": Op("/", OpType.binary, 3),
        "FloorDiv": Op("//", OpType.binary, 3),  # validate this
        "Pow": Op("**", OpType.binary, 3),  # validate this
        "Mod": Op("%", OpType.binary, 3),  # validate this
        "Not": Op("not", OpType.unary, 4),
        "Or": Op("or", OpType.binary, 5),
        "And": Op("and", OpType.binary, 6),
    }
)

for ast_node_name, op in OPS_REGISTER.items():
    if op.typ == OpType.binary:
        func = _make_binop
    else:
        assert op.typ == OpType.unary
        func = _make_unop
    setattr(CustomCodeGenerator, f"visit_{ast_node_name}", func(ast_node_name, op.name))
