"""Parser for the Tether OS command language."""

from dataclasses import dataclass
import shlex
from typing import List, Optional


class ShellSyntaxError(ValueError):
    """Raised when a command line is incomplete or ambiguous."""


@dataclass(frozen=True)
class CommandSpec:
    argv: List[str]


@dataclass(frozen=True)
class ParsedLine:
    commands: List[CommandSpec]
    redirect_path: Optional[str] = None
    append: bool = False
    background: bool = False


def parse_line(line: str) -> ParsedLine:
    lexer = shlex.shlex(line, posix=True, punctuation_chars="|>&")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError as exc:
        raise ShellSyntaxError(str(exc)) from exc

    if not tokens:
        return ParsedLine(commands=[])

    command_tokens = [[]]
    redirect_path = None
    append = False
    background = False
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "|":
            if not command_tokens[-1]:
                raise ShellSyntaxError("empty command before pipe")
            command_tokens.append([])
        elif token in {">", ">>"}:
            if redirect_path is not None:
                raise ShellSyntaxError("multiple output redirects are not supported")
            if not command_tokens[-1]:
                raise ShellSyntaxError("missing command before redirect")
            index += 1
            if index >= len(tokens) or tokens[index] in {"|", ">", ">>"}:
                raise ShellSyntaxError("missing output path after redirect")
            redirect_path = tokens[index]
            append = token == ">>"
            if index + 1 != len(tokens):
                raise ShellSyntaxError("output redirect must be the final operation")
        elif token == "&":
            if index + 1 != len(tokens):
                raise ShellSyntaxError("background marker must be the final operation")
            if not command_tokens[-1]:
                raise ShellSyntaxError("missing command before background marker")
            background = True
        elif "&" in token:
            raise ShellSyntaxError(f"unsupported operator: {token}")
        else:
            command_tokens[-1].append(token)
        index += 1

    if not command_tokens[-1]:
        raise ShellSyntaxError("empty command after pipe")

    return ParsedLine(
        commands=[CommandSpec(argv=argv) for argv in command_tokens],
        redirect_path=redirect_path,
        append=append,
        background=background,
    )
