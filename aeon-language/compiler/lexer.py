"""Aeon source lexer.

The lexer produces a stream of :class:`Token` values with stable
kinds and preserved source spans for diagnostics.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class TokenKind(Enum):
    IDENT = "IDENT"
    NUMBER = "NUMBER"
    STRING = "STRING"
    KEYWORD = "KEYWORD"
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    COLON = "COLON"
    COMMA = "COMMA"
    DOT = "DOT"
    NEWLINE = "NEWLINE"
    EOF = "EOF"


KEYWORDS = frozenset({
    "source", "recursion", "project", "into", "schedule",
    "every", "step", "integrate", "certify", "emit",
    "clock", "requires", "offers", "contract",
})


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    text: str
    line: int
    col: int
    file: str = "<stdin>"


class LexError(Exception):
    def __init__(self, message: str, line: int, col: int, file: str) -> None:
        super().__init__(f"{file}:{line}:{col}: {message}")
        self.message = message
        self.line = line
        self.col = col
        self.file = file


def tokenize(source: str, filename: str = "<stdin>") -> List[Token]:
    tokens: List[Token] = []
    line = 1
    col = 1
    i = 0
    n = len(source)

    def emit(kind: TokenKind, text: str, start_line: int, start_col: int) -> None:
        tokens.append(Token(kind, text, start_line, start_col, filename))

    while i < n:
        c = source[i]
        # Line/comment tracking
        if c == "#":
            # Comment to end of line
            while i < n and source[i] != "\n":
                i += 1
            continue
        if c == "\n":
            emit(TokenKind.NEWLINE, "\n", line, col)
            line += 1
            col = 1
            i += 1
            continue
        if c in " \t\r":
            i += 1
            col += 1
            continue

        start_line, start_col = line, col

        if c == "{":
            emit(TokenKind.LBRACE, c, start_line, start_col); i += 1; col += 1; continue
        if c == "}":
            emit(TokenKind.RBRACE, c, start_line, start_col); i += 1; col += 1; continue
        if c == "(":
            emit(TokenKind.LPAREN, c, start_line, start_col); i += 1; col += 1; continue
        if c == ")":
            emit(TokenKind.RPAREN, c, start_line, start_col); i += 1; col += 1; continue
        if c == ":":
            emit(TokenKind.COLON, c, start_line, start_col); i += 1; col += 1; continue
        if c == ",":
            emit(TokenKind.COMMA, c, start_line, start_col); i += 1; col += 1; continue
        if c == ".":
            emit(TokenKind.DOT, c, start_line, start_col); i += 1; col += 1; continue

        if c == '"':
            # String literal
            j = i + 1
            buf = []
            while j < n and source[j] != '"':
                if source[j] == "\\" and j + 1 < n:
                    buf.append(source[j:j + 2])
                    j += 2
                elif source[j] == "\n":
                    raise LexError("unterminated string literal (newline)", start_line, start_col, filename)
                else:
                    buf.append(source[j])
                    j += 1
            if j >= n:
                raise LexError("unterminated string literal (eof)", start_line, start_col, filename)
            text = "".join(buf)
            emit(TokenKind.STRING, text, start_line, start_col)
            col += (j - i + 1)
            i = j + 1
            continue

        if c.isdigit() or (c == "-" and i + 1 < n and source[i + 1].isdigit()):
            j = i
            if c == "-":
                j += 1
            while j < n and (source[j].isdigit() or source[j] in "._"):
                j += 1
            text = source[i:j]
            emit(TokenKind.NUMBER, text, start_line, start_col)
            col += (j - i)
            i = j
            continue

        if c.isalpha() or c == "_":
            j = i
            while j < n and (source[j].isalnum() or source[j] == "_"):
                j += 1
            text = source[i:j]
            kind = TokenKind.KEYWORD if text in KEYWORDS else TokenKind.IDENT
            emit(kind, text, start_line, start_col)
            col += (j - i)
            i = j
            continue

        raise LexError(f"unexpected character {c!r}", line, col, filename)

    tokens.append(Token(TokenKind.EOF, "", line, col, filename))
    return tokens
