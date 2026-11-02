"""Minimal, *non-executing* parser for WoW SavedVariables files.

SavedVariables are Lua source containing only table constructors and literals. We parse that subset
(strings, numbers, booleans, nil, nested tables with [key]=, name= and positional entries) and never
evaluate code. Anything else raises LuaParseError.
"""

import re
from typing import Any

MAX_DEPTH = 32
MAX_SIZE = 20 * 1024 * 1024

_TOKEN = re.compile(
    r"""\s*(?:
        (?P<comment>--\[(?P<eq>=*)\[.*?\](?P=eq)\]|--[^\n]*)
      | (?P<longstr>\[(?P<leq>=*)\[.*?\](?P=leq)\])
      | (?P<str>"(?:[^"\\\n]|\\.|\\\n)*"|'(?:[^'\\\n]|\\.|\\\n)*')
      | (?P<num>-?(?:0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?))
      | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
      | (?P<punct>[{}\[\]=,;])
    )""",
    re.VERBOSE | re.DOTALL,
)

_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'", "\n": "\n", "a": "\a", "b": "\b",
            "f": "\f", "v": "\v"}


class LuaParseError(ValueError):
    pass


def _unescape(body: str) -> str:
    out, i = [], 0
    while i < len(body):
        ch = body[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        i += 1
        nxt = body[i] if i < len(body) else ""
        if nxt.isdigit():
            m = re.match(r"\d{1,3}", body[i:])
            out.append(chr(int(m.group())))
            i += len(m.group())
        elif nxt == "x":
            out.append(chr(int(body[i + 1:i + 3], 16)))
            i += 3
        else:
            out.append(_ESCAPES.get(nxt, nxt))
            i += 1
    raw = "".join(out)
    try:  # WoW writes UTF-8 bytes; byte escapes (\195\169) must be re-decoded.
        return raw.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return raw


def _tokenize(src: str) -> list[tuple[str, str]]:
    tokens, pos = [], 0
    while pos < len(src):
        if src[pos:].strip() == "":
            break
        m = _TOKEN.match(src, pos)
        if not m or m.end() == pos:
            raise LuaParseError(f"unexpected input at offset {pos}: {src[pos:pos + 20]!r}")
        pos = m.end()
        if m.group("comment"):
            continue
        if m.group("longstr"):
            s = m.group("longstr")
            n = len(m.group("leq")) + 2
            body = s[n:-n]
            tokens.append(("str", body[1:] if body.startswith("\n") else body))
        elif m.group("str"):
            tokens.append(("str", _unescape(m.group("str")[1:-1])))
        elif m.group("num"):
            tokens.append(("num", m.group("num")))
        elif m.group("name"):
            tokens.append(("name", m.group("name")))
        else:
            tokens.append(("p", m.group("punct")))
    return tokens


class _Parser:
    def __init__(self, tokens):
        self.t, self.i = tokens, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else ("eof", "")

    def take(self, kind=None, value=None):
        tok = self.peek()
        if (kind and tok[0] != kind) or (value is not None and tok[1] != value):
            raise LuaParseError(f"expected {value or kind}, got {tok[1]!r}")
        self.i += 1
        return tok

    def value(self, depth=0):
        if depth > MAX_DEPTH:
            raise LuaParseError("tables nested too deeply")
        kind, v = self.peek()
        if kind == "str":
            self.i += 1
            return v
        if kind == "num":
            self.i += 1
            if v.lower().startswith(("0x", "-0x")):
                return int(v, 16)
            f = float(v)
            return int(f) if re.fullmatch(r"-?\d+", v) else f
        if kind == "name" and v in ("true", "false", "nil"):
            self.i += 1
            return {"true": True, "false": False, "nil": None}[v]
        if kind == "p" and v == "{":
            return self.table(depth + 1)
        raise LuaParseError(f"unexpected token {v!r}")

    def table(self, depth):
        self.take("p", "{")
        hashed: dict[Any, Any] = {}
        array: list[Any] = []
        while self.peek() != ("p", "}"):
            kind, v = self.peek()
            if kind == "p" and v == "[":
                self.take()
                key = self.value(depth)
                self.take("p", "]")
                self.take("p", "=")
                hashed[key] = self.value(depth)
            elif kind == "name" and self.t[self.i + 1:self.i + 2] == [("p", "=")]:
                self.i += 2
                hashed[v] = self.value(depth)
            else:
                array.append(self.value(depth))
            if self.peek()[0] == "p" and self.peek()[1] in (",", ";"):
                self.take()
        self.take("p", "}")
        # Lua arrays serialize as [1]=..,[2]=..; normalize contiguous integer keys to a list.
        if not array and hashed and all(isinstance(k, int) for k in hashed) and \
                sorted(hashed) == list(range(1, len(hashed) + 1)):
            return [hashed[k] for k in range(1, len(hashed) + 1)]
        if array and not hashed:
            return array
        if array:
            for idx, item in enumerate(array, start=1):
                hashed.setdefault(idx, item)
        return hashed


def parse_savedvariables(src: str) -> dict[str, Any]:
    """Parse ``Name = value`` assignments from a SavedVariables file into a dict."""
    if len(src) > MAX_SIZE:
        raise LuaParseError("file too large")
    p = _Parser(_tokenize(src))
    out: dict[str, Any] = {}
    while p.peek()[0] != "eof":
        name = p.take("name")[1]
        p.take("p", "=")
        out[name] = p.value()
    return out


def savedvariables_to_envelope(data: dict[str, Any]) -> dict[str, Any]:
    """Convert the AzerothChroniclesDB table written by the addon into an ingestion envelope dict."""
    db = data.get("AzerothChroniclesDB")
    if not isinstance(db, dict):
        raise LuaParseError("AzerothChroniclesDB not found; is this the AzerothChronicles.lua SavedVariables file?")
    chars = db.get("characters") or {}
    if isinstance(chars, dict):
        chars = [dict(v, guid=v.get("guid", k)) for k, v in chars.items() if isinstance(v, dict)]
    records = db.get("records") or []
    if isinstance(records, dict):
        records = [records[k] for k in sorted(records, key=str)]
    for r in records:
        if isinstance(r, dict) and isinstance(r.get("roster"), dict):
            r["roster"] = list(r["roster"].values())
    return {"format": "azeroth-chronicles/v1", "source": "addon", "addon_version": db.get("version"),
            "exported_at": db.get("lastWrite"), "characters": chars, "records": records}
