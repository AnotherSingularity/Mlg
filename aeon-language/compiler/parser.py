"""Aeon source parser (recursive descent).

Consumes the token stream from :mod:`.lexer` and produces a
:class:`~.ast.Module`. Diagnostics are source-located.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from .ast import (
    CertifyStmt,
    EmitStmt,
    EveryBlock,
    IntegrateStmt,
    Module,
    ProjectionDecl,
    RecursionDecl,
    ScheduleDecl,
    SourceDecl,
    Span,
    StepStmt,
)
from .lexer import Token, TokenKind, tokenize


class ParseError(Exception):
    def __init__(self, message: str, line: int, col: int, file: str) -> None:
        super().__init__(f"{file}:{line}:{col}: parse error: {message}")
        self.message = message
        self.line = line
        self.col = col
        self.file = file


class Parser:
    def __init__(self, tokens: List[Token], module_id: str) -> None:
        self.tokens = tokens
        self.i = 0
        self.module_id = module_id

    # ---- token helpers -------------------------------------------------

    def peek(self, k: int = 0) -> Token:
        return self.tokens[min(self.i + k, len(self.tokens) - 1)]

    def eat(self) -> Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def eat_kind(self, kind: TokenKind) -> Token:
        tok = self.tokens[self.i]
        if tok.kind is not kind:
            self._error(f"expected {kind.value}, got {tok.kind.value} ({tok.text!r})", tok)
        self.i += 1
        return tok

    def match_keyword(self, text: str) -> bool:
        tok = self.tokens[self.i]
        return tok.kind is TokenKind.KEYWORD and tok.text == text

    def eat_keyword(self, text: str) -> Token:
        tok = self.tokens[self.i]
        if not (tok.kind is TokenKind.KEYWORD and tok.text == text):
            self._error(f"expected keyword {text!r}, got {tok.text!r}", tok)
        self.i += 1
        return tok

    def skip_newlines(self) -> None:
        while self.tokens[self.i].kind is TokenKind.NEWLINE:
            self.i += 1

    def _span(self, tok: Token) -> Span:
        return Span(tok.line, tok.col, tok.file)

    def _error(self, message: str, tok: Token) -> None:
        raise ParseError(message, tok.line, tok.col, tok.file)

    # ---- top-level -----------------------------------------------------

    def parse(self) -> Module:
        sources: List[SourceDecl] = []
        recursions: List[RecursionDecl] = []
        projections: List[ProjectionDecl] = []
        schedule: Optional[ScheduleDecl] = None

        self.skip_newlines()
        while self.peek().kind is not TokenKind.EOF:
            self.skip_newlines()
            if self.peek().kind is TokenKind.EOF:
                break
            if self.match_keyword("source"):
                sources.append(self._parse_source())
            elif self.match_keyword("recursion"):
                recursions.append(self._parse_recursion())
            elif self.match_keyword("project"):
                projections.append(self._parse_projection())
            elif self.match_keyword("schedule"):
                if schedule is not None:
                    self._error("duplicate 'schedule' block", self.peek())
                schedule = self._parse_schedule()
            else:
                tok = self.peek()
                self._error(f"unexpected token {tok.text!r} at top level", tok)
            self.skip_newlines()

        # Sort sources / recursions / projections by name for determinism.
        return Module(
            module_id=self.module_id,
            sources=tuple(sorted(sources, key=lambda s: s.name)),
            recursions=tuple(sorted(recursions, key=lambda r: r.name)),
            projections=tuple(
                sorted(projections, key=lambda p: (p.source, p.port, p.substrate))
            ),
            schedule=schedule,
        )

    # ---- source --------------------------------------------------------

    def _parse_source(self) -> SourceDecl:
        kw = self.eat_keyword("source")
        name_tok = self.eat_kind(TokenKind.IDENT)
        self.eat_kind(TokenKind.COLON)
        impl_tok = self.eat_kind(TokenKind.IDENT)
        body = self._parse_attribute_block()
        clock = body.pop("clock", None)
        requires = tuple(sorted(self._as_list(body.pop("requires", None))))
        offers = tuple(sorted(self._as_list(body.pop("offers", None))))
        attributes = tuple(sorted(body.items()))
        return SourceDecl(
            name=name_tok.text,
            impl_type=impl_tok.text,
            clock=clock,
            requires=requires,
            offers=offers,
            attributes=attributes,
            span=self._span(kw),
        )

    # ---- recursion -----------------------------------------------------

    def _parse_recursion(self) -> RecursionDecl:
        kw = self.eat_keyword("recursion")
        name_tok = self.eat_kind(TokenKind.IDENT)
        self.eat_kind(TokenKind.COLON)
        impl_tok = self.eat_kind(TokenKind.IDENT)
        body = self._parse_attribute_block()
        clock = body.pop("clock", None)
        dim = body.pop("dimension", None)
        margin = body.pop("contraction_margin", None)
        attributes = tuple(sorted(body.items()))
        return RecursionDecl(
            name=name_tok.text,
            impl_type=impl_tok.text,
            clock=clock,
            dimension=int(dim) if dim is not None else None,
            contraction_margin=float(margin) if margin is not None else None,
            attributes=attributes,
            span=self._span(kw),
        )

    # ---- projection ----------------------------------------------------

    def _parse_projection(self) -> ProjectionDecl:
        kw = self.eat_keyword("project")
        source_tok = self.eat_kind(TokenKind.IDENT)
        self.eat_kind(TokenKind.DOT)
        port_tok = self.eat_kind(TokenKind.IDENT)
        self.eat_keyword("into")
        substrate_tok = self.eat_kind(TokenKind.IDENT)
        return ProjectionDecl(
            source=source_tok.text,
            port=port_tok.text,
            substrate=substrate_tok.text,
            span=self._span(kw),
        )

    # ---- schedule ------------------------------------------------------

    def _parse_schedule(self) -> ScheduleDecl:
        kw = self.eat_keyword("schedule")
        self.eat_kind(TokenKind.LBRACE)
        self.skip_newlines()
        blocks: List[EveryBlock] = []
        while self.peek().kind is not TokenKind.RBRACE:
            self.skip_newlines()
            if self.peek().kind is TokenKind.RBRACE:
                break
            if not self.match_keyword("every"):
                self._error("expected 'every' inside schedule block", self.peek())
            blocks.append(self._parse_every())
            self.skip_newlines()
        self.eat_kind(TokenKind.RBRACE)
        return ScheduleDecl(blocks=tuple(blocks), span=self._span(kw))

    def _parse_every(self) -> EveryBlock:
        kw = self.eat_keyword("every")
        # `every N clock` or `every clock`
        nxt = self.peek()
        if nxt.kind is TokenKind.NUMBER:
            n_tok = self.eat_kind(TokenKind.NUMBER)
            n = int(float(n_tok.text))
        else:
            n = 1
        clock_tok = self.eat()
        if clock_tok.kind not in (TokenKind.IDENT, TokenKind.KEYWORD):
            self._error("expected clock name after 'every'", clock_tok)
        self.eat_kind(TokenKind.LBRACE)
        self.skip_newlines()
        body: List[Any] = []
        while self.peek().kind is not TokenKind.RBRACE:
            self.skip_newlines()
            if self.peek().kind is TokenKind.RBRACE:
                break
            body.append(self._parse_schedule_stmt())
            self.skip_newlines()
        self.eat_kind(TokenKind.RBRACE)
        return EveryBlock(every=n, clock=clock_tok.text, body=tuple(body), span=self._span(kw))

    def _parse_schedule_stmt(self) -> Any:
        tok = self.peek()
        if tok.kind is not TokenKind.KEYWORD:
            self._error("expected schedule statement", tok)
        if tok.text == "step":
            self.eat()
            target = self.eat_kind(TokenKind.IDENT).text
            return StepStmt(target=target, span=self._span(tok))
        if tok.text == "integrate":
            self.eat()
            target = self.eat_kind(TokenKind.IDENT).text
            return IntegrateStmt(target=target, span=self._span(tok))
        if tok.text == "certify":
            self.eat()
            target = self.eat_kind(TokenKind.IDENT).text
            return CertifyStmt(target=target, span=self._span(tok))
        if tok.text == "emit":
            self.eat()
            target = self.eat_kind(TokenKind.IDENT).text
            return EmitStmt(target=target, span=self._span(tok))
        self._error(f"unknown schedule statement {tok.text!r}", tok)
        raise AssertionError  # unreachable

    # ---- attribute block ----------------------------------------------

    def _parse_attribute_block(self) -> dict:
        self.eat_kind(TokenKind.LBRACE)
        self.skip_newlines()
        attrs: dict = {}
        while self.peek().kind is not TokenKind.RBRACE:
            self.skip_newlines()
            if self.peek().kind is TokenKind.RBRACE:
                break
            key_tok = self.eat()
            if key_tok.kind not in (TokenKind.IDENT, TokenKind.KEYWORD):
                self._error("expected attribute name", key_tok)
            self.eat_kind(TokenKind.COLON)
            value = self._parse_value()
            if key_tok.text in attrs:
                self._error(f"duplicate attribute {key_tok.text!r}", key_tok)
            attrs[key_tok.text] = value
            self.skip_newlines()
        self.eat_kind(TokenKind.RBRACE)
        return attrs

    def _parse_value(self) -> Any:
        tok = self.peek()
        if tok.kind is TokenKind.NUMBER:
            self.eat()
            text = tok.text
            if any(ch in text for ch in "._"):
                return float(text.replace("_", ""))
            return int(text)
        if tok.kind is TokenKind.STRING:
            self.eat()
            return tok.text
        if tok.kind is TokenKind.IDENT or tok.kind is TokenKind.KEYWORD:
            # Comma-separated list or single identifier
            first = self.eat().text
            items = [first]
            while self.peek().kind is TokenKind.COMMA:
                self.eat()
                nxt = self.eat()
                if nxt.kind not in (TokenKind.IDENT, TokenKind.KEYWORD):
                    self._error("expected identifier in list value", nxt)
                items.append(nxt.text)
            if len(items) == 1:
                return items[0]
            return items
        self._error(f"unexpected token {tok.text!r} in value", tok)
        raise AssertionError

    def _as_list(self, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return list(value)
        return [value]


def parse(source: str, filename: str = "<stdin>", *, module_id: Optional[str] = None) -> Module:
    tokens = tokenize(source, filename)
    parser = Parser(tokens, module_id=module_id or filename)
    return parser.parse()
