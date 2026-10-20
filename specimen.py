"""The specimen images: Motif Code at work in an editor, highlighted the way
Microtone's Motif editor highlights code — in Syntello, the light colour
scheme its code colours follow (specimen/Syntello.v1.icls, an IntelliJ
scheme, read here as it stands) — and every weight at a glance.

Drawn with Pillow from the static fonts the build has just made, at 40 px:
every advance Motif Code has (450, 600, 750 and 1200 units) is then a whole
number of pixels, so token after token lands where an editor would put it.

TML is highlighted by a port of the Motif editor's own rules, run over the
whole program so that a name declared anywhere in it is drawn as what it is;
Python and JavaScript are lexed by Pygments and coloured with the scheme's
attributes for each kind of token, the way IntelliJ draws them.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 40          # px: the code, at twice an editor's 20 px
LINE = 60          # px from one baseline to the next
LABEL = 30         # px: line numbers and the tab's file name
RADIUS = 20        # px: the window's corners


# ── the colour scheme ───────────────────────────────────────────────────────

class Scheme:
    """An IntelliJ .icls: its editor colours and its text attributes, each
    attribute resolved through its baseAttributes (what the scheme leaves out
    is the text's own colour)."""

    def __init__(self, path):
        root = ET.parse(path).getroot()
        self.colors = {o.get("name"): _hex(o.get("value")) for o in root.find("colors")
                       if o.get("value")}
        self.attrs = {}
        for o in root.find("attributes"):
            v = o.find("value")
            own = {p.get("name"): p.get("value") for p in v} if v is not None else {}
            self.attrs[o.get("name")] = (o.get("baseAttributes"), own)
        text = self.attrs["TEXT"][1]
        self.fg, self.bg = _hex(text["FOREGROUND"]), _hex(text["BACKGROUND"])

    def resolve(self, key):
        merged, seen = {}, set()
        while key and key not in seen:
            seen.add(key)
            base, own = self.attrs.get(key, (None, {}))
            for k, v in own.items():
                merged.setdefault(k, v)
            key = base
        return merged

    def style(self, key):
        """(colour, bold, italic) for a text attribute; None is plain text,
        and a "+bold" after the name makes it bold whatever the scheme says."""
        if key is None:
            return self.fg, False, False
        key, _, extra = key.partition("+")
        a = self.resolve(key)
        kind = int(a.get("FONT_TYPE", "0")) | (1 if extra == "bold" else 0)
        return _hex(a["FOREGROUND"]) if a.get("FOREGROUND") else self.fg, bool(kind & 1), bool(kind & 2)

    def background(self, key):
        b = self.resolve(key).get("BACKGROUND")
        return _hex(b) if b else None


def _hex(v):
    """An IntelliJ colour: hex digits without their leading zeros."""
    return "#" + v.rjust(6, "0")


# ── TML, as the Motif editor highlights it ──────────────────────────────────

TML_KEYWORDS = {"tml", "let", "fn", "for", "in", "while", "if", "then", "else", "return", "break",
                "continue", "and", "or", "not", "true", "false", "none"}
DECL_BLOCK, DECL_NAMED = {"song", "master"}, {"instrument", "lane"}
TML_BUILTINS = set("""PI abs acos all any asin assert at atan atan2 bar_of ceil cell cells chance choose
choose_weighted clamp contains copy cos count cut db degree dir dir_arg ends_with error exp fade filter
flatten floor follow fx fx2 get glide glide_speed has_key hit index_of insert invert join keyoff keys lanes
len list log log10 log2 loop lower map map_notes map_vols max melody merge midi min mirror nearest_chord
noise note note_name notes num occupied on period pop print push random random_int range reduce remove
repeat replace rest reverse rotate round row_in_bar scan seed seq set_pan set_vol shift shuffle sign sin
slice sort split sqrt stack starts_with str stretch sum tan transpose trim trunc type under unique upper
values vibrato vol_fine vol_ramp vol_slide with word zip""".split())
TML_OPS = ["..<", "...", "**", "..", "==", "!=", "<=", ">=", "<<", ">>", "+=", "-=", "*=", "/=", "=>",
           "(", ")", "[", "]", "{", "}", ",", ":", ";", ".", "=", "<", ">", "+", "-", "*", "/", "%",
           "&", "|", "^", "~"]
PUNCT = set("()[]{},;.")
OPEN, CLOSE = {"(": ")", "[": "]", "{": "}"}, {")", "]", "}"}
CONTINUES = {"then", "else", "and", "or", "not"}  # a line that starts or ends with one goes on

# The Motif editor's classes, as the Syntello attributes its colours follow
# (the editor draws a declaration word bold, in the scheme's second keyword
# colour).
TML_ATTR = {
    "t-kw": "DEFAULT_KEYWORD", "t-decl": "CUSTOM_KEYWORD2_ATTRIBUTES+bold", "t-num": "DEFAULT_NUMBER",
    "t-str": "DEFAULT_STRING", "t-esc": "DEFAULT_VALID_STRING_ESCAPE", "t-pitch": "DEFAULT_CONSTANT",
    "t-com": "DEFAULT_LINE_COMMENT", "t-fn": "DEFAULT_FUNCTION_CALL", "t-bi": "DEFAULT_STATIC_METHOD",
    "t-fnd": "DEFAULT_FUNCTION_DECLARATION", "t-fld": "DEFAULT_INSTANCE_FIELD", "t-par": "DEFAULT_PARAMETER",
    "t-op": "DEFAULT_OPERATION_SIGN", "t-name": "DEFAULT_STATIC_FIELD",
}


def _tml_scan(src):
    """Source → [[kind, text]]: ws, com, str, pitch, num, id, op."""
    toks, i, n = [], 0, len(src)
    hexd = set("0123456789abcdefABCDEF")
    while i < n:
        c, start = src[i], i
        if c in " \t\r\n":
            while i < n and src[i] in " \t\r\n":
                i += 1
            toks.append(["ws", src[start:i]])
        elif src.startswith("//", i):
            while i < n and src[i] != "\n":
                i += 1
            toks.append(["com", src[start:i]])
        elif src.startswith("/*", i):
            e = src.find("*/", i + 2)
            i = n if e < 0 else e + 2
            toks.append(["com", src[start:i]])
        elif c == '"':
            triple = src.startswith('"""', i)
            i = _string_end(src, i + (3 if triple else 1), triple)
            toks.append(["str", src[start:i]])
        elif c == "'":
            i += 1
            while i < n and src[i] not in "'\n":
                i += 1
            i += src[i:i + 1] == "'"
            toks.append(["pitch", src[start:i]])
        elif c.isdigit() or (c == "$" and src[i + 1:i + 2] in hexd and src[i + 1:i + 2]):
            if c == "$" or src[i:i + 2] in ("0x", "0X"):
                i += 1 if c == "$" else 2
                while i < n and src[i] in hexd:
                    i += 1
            else:
                while i < n and src[i].isdigit():
                    i += 1
                if src[i:i + 1] == "." and src[i + 1:i + 2].isdigit():
                    i += 1
                    while i < n and src[i].isdigit():
                        i += 1
            while i < n and (src[i].isalnum() or src[i] == "_"):
                i += 1
            toks.append(["num", src[start:i]])
        elif c.isalpha() or c == "_":
            while i < n and (src[i].isalnum() or src[i] == "_"):
                i += 1
            toks.append(["id", src[start:i]])
        else:
            op = next((o for o in TML_OPS if src.startswith(o, i)), c)
            i += len(op)
            toks.append(["op", op])
    return toks


def _string_end(src, i, triple):
    n = len(src)
    while i < n:
        if triple and src.startswith('"""', i):
            return i + 3
        if not triple and src[i] == '"':
            return i + 1
        if not triple and src[i] == "\n":
            return i
        i += 2 if src[i] == "\\" else 1
    return n


def _string_runs(s):
    """A string token as (text, class) runs: its escapes and ${…} marks apart."""
    out, lit, i = [], "", 0
    while i < len(s):
        if s[i] == "\\":
            out += [(lit, "t-str"), (s[i:i + 2], "t-esc")]
            lit, i = "", i + 2
        elif s.startswith("${", i):
            out += [(lit, "t-str"), ("${", "t-esc")]
            lit, i = "", i + 2
        elif s[i] == "}" and any(t == "${" for t, _ in out):
            out += [(lit, "t-str"), ("}", "t-esc")]
            lit, i = "", i + 1
        else:
            lit += s[i]
            i += 1
    return [r for r in out + [(lit, "t-str")] if r[0]]


def tml_runs(src):
    """TML → [(text, attribute, underline)], every character once, in order."""
    toks = _tml_scan(src)
    sig = [i for i, t in enumerate(toks) if t[0] not in ("ws", "com")]
    cls = [None] * len(toks)
    tok = lambda si: toks[sig[si]] if 0 <= si < len(sig) else None  # noqa: E731

    def starts_statement(si):
        if si == 0:
            return True
        prev = tok(si - 1)
        if prev[1] in (";", "{", "}"):
            return True
        return any("\n" in t[1] for t in toks[sig[si - 1] + 1:sig[si]])

    # where each bracket closes
    match, stack = {}, []
    for si in range(len(sig)):
        t = tok(si)
        if t[0] == "op" and t[1] in OPEN:
            stack.append(si)
        elif t[0] == "op" and t[1] in CLOSE and stack:
            match[stack.pop()] = si
    enclosing = {}  # sig index → the bracket it sits inside
    stack = []
    for si in range(len(sig)):
        t = tok(si)
        if t[0] == "op" and t[1] in CLOSE and stack:
            stack.pop()
        enclosing[si] = stack[-1] if stack else None
        if t[0] == "op" and t[1] in OPEN:
            stack.append(si)

    # the editor's rules: what each token is by where it stands
    param_depth, expect_params, line_has_range = 0, False, False
    for si in range(len(sig)):
        ti, t = sig[si], tok(si)
        prev, nxt, nxt2 = tok(si - 1), tok(si + 1), tok(si + 2)
        if t[0] == "op":
            if t[1] in ("..", "..<"):
                line_has_range = True
            if t[1] == "(" and expect_params:
                param_depth, expect_params = 1, False
            elif param_depth > 0:
                param_depth += t[1] in OPEN
                param_depth -= t[1] in CLOSE
            if t[1] not in PUNCT:
                cls[ti] = "t-op"
            continue
        if t[0] in ("num", "pitch"):
            cls[ti] = "t-" + t[0]
            continue
        if t[0] != "id":
            continue
        w, first = t[1], starts_statement(si)
        if first:
            line_has_range = False
        if w in TML_KEYWORDS:
            cls[ti] = "t-kw"
            expect_params = expect_params or w == "fn"
        elif first and w in DECL_BLOCK and nxt and nxt[1] == "{":
            cls[ti] = "t-decl"
        elif first and w in DECL_NAMED and nxt and nxt[0] == "id" and nxt2 and nxt2[1] == "{":
            cls[ti], cls[sig[si + 1]] = "t-decl", "t-name"
        elif first and w == "section" and nxt and nxt[0] == "str":
            cls[ti] = "t-decl"
        elif w == "by" and line_has_range:
            cls[ti] = "t-kw"
        elif prev and prev[1] == "fn" and prev[0] == "id":
            cls[ti], expect_params = "t-fnd", True
        elif param_depth == 1 and nxt and nxt[1] in (",", ")", "="):
            cls[ti] = "t-par"
        elif nxt and nxt[1] == "(":
            cls[ti] = "t-bi" if w in TML_BUILTINS else "t-fn"
        elif (nxt and nxt[1] == ":") or (prev and prev[1] == "."):
            cls[ti] = "t-fld"

    # what each name refers to, as the editor's analysis has it: parameters
    # and the names a block, a loop or a function declares, within their
    # reach; the song's lanes and instruments wherever they are named
    scopes = []  # (first sig, last sig, {name: class})
    globals_ = {tok(si + 1)[1] for si in range(len(sig) - 2)
                if tok(si)[1] in DECL_NAMED and starts_statement(si) and tok(si + 1)[0] == "id"}
    end = len(sig) - 1

    def expression_end(si):
        """The last token of the expression that starts at si: where the
        next statement starts, or where a bracket it is inside closes."""
        depth = 0
        for sj in range(si, len(sig)):
            t = tok(sj)
            if t[0] == "op" and t[1] in OPEN:
                depth += 1
            elif t[0] == "op" and t[1] in CLOSE:
                if depth == 0:
                    return sj - 1
                depth -= 1
            nxt = tok(sj + 1)
            if depth == 0 and (nxt is None or (starts_statement(sj + 1) and nxt[1] not in CONTINUES
                                                and not (t[0] == "op" and t[1] not in CLOSE)
                                                and t[1] not in CONTINUES)):
                return sj
        return end

    for si in range(len(sig)):
        t = tok(si)
        if t[0] == "id" and t[1] == "fn":
            sj = si + 1
            if tok(sj) and tok(sj)[0] == "id" and tok(sj)[1] not in TML_KEYWORDS:
                sj += 1
            if not (tok(sj) and tok(sj)[1] == "("):
                continue
            close = match.get(sj, end)
            names = {tok(k)[1]: "t-par" for k in range(sj + 1, close)
                     if tok(k)[0] == "id" and enclosing[k] == sj and tok(k + 1)[1] in (",", ")", "=")}
            body = close + 1
            if tok(body) and tok(body)[1] == "{":
                scopes.append((body, match.get(body, end), names))
            elif tok(body) and tok(body)[1] == "=>":
                scopes.append((body, expression_end(body + 1), names))
        elif t[0] == "id" and t[1] == "for":
            names, sj = {}, si + 1
            while tok(sj) and tok(sj)[1] != "in":
                if tok(sj)[0] == "id":
                    names[tok(sj)[1]] = "t-loc"
                sj += 1
            if starts_statement(si):
                block = next((k for k in range(sj, len(sig)) if tok(k)[1] == "{" and enclosing[k] == enclosing[si]),
                             None)
                if block is not None:
                    scopes.append((si, match.get(block, end), names))
            elif enclosing[si] is not None:
                scopes.append((enclosing[si], match.get(enclosing[si], end), names))
        elif t[0] == "id" and t[1] == "let" and enclosing[si] is not None and tok(si + 1)[0] == "id":
            scopes.append((si, match.get(enclosing[si], end), {tok(si + 1)[1]: "t-loc"}))

    underline = [False] * len(toks)
    for si in range(len(sig)):
        ti, t = sig[si], tok(si)
        prev, nxt = tok(si - 1), tok(si + 1)
        if t[0] != "id" or t[1] in TML_KEYWORDS or (prev and prev[1] == ".") \
                or (nxt and nxt[1] == ":" and cls[ti] == "t-fld"):
            continue
        found = None
        for a, b, names in scopes:
            if a <= si <= b and t[1] in names and (found is None or a >= found[0]):
                found = (a, names[t[1]])
        if found and found[1] == "t-loc":
            underline[ti] = True
        elif found:
            cls[ti] = found[1]
        elif t[1] in globals_ and cls[ti] not in ("t-decl",):
            cls[ti] = "t-name"

    runs = []
    for ti, (kind, text) in enumerate(toks):
        if kind == "ws":
            runs.append((text, None, False))
        elif kind == "com":
            runs.append((text, TML_ATTR["t-com"], False))
        elif kind == "str":
            runs += [(s, TML_ATTR[c], False) for s, c in _string_runs(text)]
        else:
            runs.append((text, TML_ATTR.get(cls[ti]), underline[ti]))
    return runs


# ── Python and JavaScript, through Pygments ─────────────────────────────────

def pygments_runs(code, language):
    """Code → [(text, attribute, underline)], coloured the way IntelliJ
    colours each kind of token: declarations, calls, fields, parameters (and
    their uses), JavaScript's local and global variables."""
    from pygments.lexers import get_lexer_by_name
    from pygments.token import Comment, Keyword, Name, Number, Operator, Punctuation, String

    toks = list(get_lexer_by_name(language, stripnl=False, ensurenl=False).get_tokens(code))
    texts = [s for _, s in toks]
    lines = []  # the line each token starts on
    row = 0
    for s in texts:
        lines.append(row)
        row += s.count("\n")
    indents = [len(l) - len(l.lstrip()) if l.strip() else None for l in code.split("\n")]
    sig = [i for i, (t, s) in enumerate(toks) if s.strip() and t not in Comment and t not in String.Doc]
    pos = {ti: si for si, ti in enumerate(sig)}
    keys = [None] * len(toks)
    scopes = []  # [names, kind, limit]: python (def indent), brace (depth)
    depth = 0
    pending = None  # parameters being collected: [names, kind, limit, paren depth]
    arrow_from = None
    js = language in ("javascript", "js")

    def text(si):
        return texts[sig[si]] if 0 <= si < len(sig) else ""

    for ti, (t, s) in enumerate(toks):
        if t in Comment:
            keys[ti] = ("DEFAULT_DOC_COMMENT" if s.startswith("/**") else
                        "DEFAULT_BLOCK_COMMENT" if s.startswith("/*") else "DEFAULT_LINE_COMMENT")
            continue
        if t in String.Doc:
            keys[ti] = "DEFAULT_DOC_COMMENT"
            continue
        if ti not in pos:
            continue
        si = pos[ti]
        # Python: a line indented no deeper than a def's ends its body
        if not js and (si == 0 or lines[sig[si - 1]] != lines[ti]):
            ind = indents[lines[ti]]
            scopes = [sc for sc in scopes if sc[1] != "py" or (ind is not None and ind > sc[2])]
        if t in Punctuation or t in Operator:
            if s in ("{", "(", "["):
                depth += 1
            elif s in ("}", ")", "]"):
                depth -= 1
                scopes = [sc for sc in scopes if sc[1] != "brace" or depth >= sc[2]]
            if pending and s == "(" and pending[3] is None:
                pending[3] = depth
            elif pending and s == ")" and pending[3] is not None and depth < pending[3]:
                names, kind, limit, _ = pending
                if js:
                    limit = depth + 1  # the body's braces
                scopes.append([names, kind, limit])
                pending = None
            if s == "=>" and text(si - 1) == ")":
                # an arrow function's parameters reach to the end of its line
                k, d, names = si - 1, 0, {}
                while k >= 0:
                    d += text(k) == ")"
                    d -= text(k) == "("
                    if d == 0:
                        break
                    k -= 1
                for kk in range(k + 1, si - 1):
                    if toks[sig[kk]][0] in Name and text(kk + 1) in (",", ")", "="):
                        names[text(kk)] = "DEFAULT_PARAMETER"
                        keys[sig[kk]] = "DEFAULT_PARAMETER"
                scopes.append([names, "line", lines[ti]])
            keys[ti] = "DEFAULT_OPERATION_SIGN" if (t in Operator and t not in Operator.Word) or s == "=>" \
                else ("DEFAULT_KEYWORD" if t in Operator.Word else None)
            continue
        scopes = [sc for sc in scopes if sc[1] != "line" or lines[ti] == sc[2]]
        if t in String.Escape or t in String.Interpol:
            keys[ti] = "DEFAULT_VALID_STRING_ESCAPE"
        elif t in String:
            keys[ti] = "DEFAULT_STRING"
        elif t in Number:
            keys[ti] = "DEFAULT_NUMBER"
        elif t in Keyword:
            keys[ti] = "DEFAULT_KEYWORD"
        elif t in Name.Decorator:
            keys[ti] = "DEFAULT_METADATA"
        elif t in Name:
            prev, nxt = text(si - 1), text(si + 1)
            if prev in ("def", "function"):
                keys[ti] = "DEFAULT_FUNCTION_DECLARATION"
                ind = indents[lines[ti]] or 0
                pending = [{}, "brace" if js else "py", ind, None]
            elif pending and pending[3] is not None and depth == pending[3] and nxt in (",", ")", "=", ":"):
                keys[ti] = "DEFAULT_PARAMETER"
                pending[0][s] = "DEFAULT_PARAMETER"
            elif prev == ".":
                keys[ti] = "DEFAULT_FUNCTION_CALL" if nxt == "(" else "DEFAULT_INSTANCE_FIELD"
            elif nxt == "(" and t in Name.Builtin:
                keys[ti] = "DEFAULT_STATIC_METHOD"
            elif nxt == "(":
                keys[ti] = "DEFAULT_FUNCTION_CALL"
            elif js and nxt == ":" and prev in ("{", ","):
                keys[ti] = "DEFAULT_INSTANCE_FIELD"
            elif js and prev in ("const", "let", "var"):
                kind = "JS.LOCAL_VARIABLE" if depth > 0 else "JS.GLOBAL_VARIABLE"
                keys[ti] = kind
                scopes.append([{s: kind}, "brace", depth])
            else:
                for names, _, _ in reversed(scopes):
                    if s in names:
                        keys[ti] = names[s]
                        break
                else:
                    keys[ti] = None
    return [(s, k, False) for s, k in zip(texts, keys)]


# ── drawing ─────────────────────────────────────────────────────────────────

def _lines(runs):
    """Runs with newlines in them → one list of runs per line."""
    out = [[]]
    for text, key, under in runs:
        parts = text.expandtabs(4).split("\n")
        for i, p in enumerate(parts):
            if i:
                out.append([])
            if p:
                out[-1].append((p, key, under))
    return out


def excerpt(path, start, end):
    """The lines of `path` from the first that starts with `start` up to the
    first after it that starts with `end` (trailing blank lines dropped), and
    the number of the first."""
    lines = Path(path).read_text().split("\n")
    a = next(i for i, l in enumerate(lines) if l.startswith(start))
    b = next((i for i in range(a + 1, len(lines)) if lines[i].startswith(end)), len(lines)) if end else len(lines)
    while b > a and not lines[b - 1].strip():
        b -= 1
    return a, b


def render_editor(runs, first, count, scheme, faces, title, caret, out):
    """An editor window showing `count` lines of `runs` from line `first`
    (0-based), the caret in the `caret[1]`-th occurrence of the name
    caret[0] and every occurrence of it marked, as IntelliJ marks them."""
    all_lines = _lines(runs)
    rows = all_lines[first:first + count]
    font = lambda bold, italic: faces[(bold, italic)]  # noqa: E731
    label = faces["label"]
    styled = []
    for row in rows:
        line, x = [], 0
        for text, key, under in row:
            colour, bold, italic = scheme.style(key)
            f = font(bold, italic)
            w = f.getlength(text)
            line.append((text, colour, f, x, w, under))
            x += w
        styled.append(line)
    cell = font(False, False).getlength("0")
    numbers = [str(first + 1 + i) for i in range(len(rows))]
    gutter = round(label.getlength("0") * max(len(n) for n in numbers) + 2 * cell + 16)
    tab_h, pad_top, pad_x = 76, 22, round(cell)
    width = gutter + pad_x + round(max((l[-1][3] + l[-1][4]) if l else 0 for l in styled)) + 3 * pad_x
    height = tab_h + pad_top + len(rows) * LINE + pad_top
    img = Image.new("RGB", (width, height), scheme.bg)
    d = ImageDraw.Draw(img)

    # the name under the caret and its occurrences
    name, nth = caret
    hits = [(r, item) for r, line in enumerate(styled) for item in line if item[0] == name]
    caret_row, caret_item = hits[min(nth, len(hits) - 1)] if hits else (0, None)
    top = lambda r: tab_h + pad_top + r * LINE  # noqa: E731
    x0 = gutter + pad_x
    d.rectangle((gutter, top(caret_row), width, top(caret_row) + LINE - 1), fill=scheme.colors["CARET_ROW_COLOR"])
    read = scheme.background("IDENTIFIER_UNDER_CARET_ATTRIBUTES")
    write = scheme.background("WRITE_IDENTIFIER_UNDER_CARET_ATTRIBUTES")
    for k, (r, item) in enumerate(hits):
        _, _, _, x, w, _ = item
        d.rectangle((x0 + x, top(r) + 6, x0 + x + w - 1, top(r) + LINE - 7), fill=write if k == 0 else read)

    # the gutter and the tab bar
    d.rectangle((0, tab_h, gutter - 1, height), fill=scheme.colors["GUTTER_BACKGROUND"])
    d.rectangle((0, 0, width, tab_h - 1), fill=scheme.colors["GUTTER_BACKGROUND"])
    tab_w = round(label.getlength(title)) + 2 * 32
    d.rectangle((0, 0, tab_w, tab_h - 1), fill=scheme.bg)
    d.rectangle((0, tab_h - 4, tab_w, tab_h - 1), fill=scheme.colors["LINE_NUMBER_ON_CARET_ROW_COLOR"])
    d.line((0, tab_h - 1, width, tab_h - 1), fill=scheme.colors["TEARLINE_COLOR"], width=1)
    asc, desc = font(False, False).getmetrics()
    baseline = lambda r: top(r) + (LINE - asc - desc) // 2 + asc  # noqa: E731
    d.text((32, tab_h // 2 + 2), title, font=label, fill=scheme.fg, anchor="lm")
    for r, n in enumerate(numbers):
        colour = scheme.colors["LINE_NUMBER_ON_CARET_ROW_COLOR"] if r == caret_row else scheme.colors["LINE_NUMBERS_COLOR"]
        d.text((gutter - cell - 8, baseline(r)), n, font=label, fill=colour, anchor="rs")

    # the code
    for r, line in enumerate(styled):
        for text, colour, f, x, w, under in line:
            d.text((x0 + x, baseline(r)), text, font=f, fill=colour, anchor="ls")
            if under:
                d.line((x0 + x, baseline(r) + 7, x0 + x + w - 1, baseline(r) + 7), fill=colour, width=2)
    if caret_item:
        x = x0 + caret_item[3] + round(caret_item[2].getlength(name[:2]))
        d.rectangle((x - 1, top(caret_row) + 6, x + 1, top(caret_row) + LINE - 7), fill=scheme.fg)
    _window(img, scheme).save(out)


def render_styles(fonts, scheme, text, out):
    """Every weight, roman beside italic, as a card."""
    rows = []
    for w, label, roman, italic in fonts:
        rows.append((f"{w}  {label}", ImageFont.truetype(str(roman), SIZE), ImageFont.truetype(str(italic), SIZE)))
    small = ImageFont.truetype(str(fonts[3][2]), LABEL)
    lab_w = round(max(small.getlength(r[0]) for r in rows)) + 80
    col = round(max(r[1].getlength(text) for r in rows)) + 80
    pad = 40
    width, height = pad + lab_w + 2 * col, 2 * pad + len(rows) * 72
    img = Image.new("RGB", (width, height), scheme.bg)
    d = ImageDraw.Draw(img)
    for i, (label, roman, italic) in enumerate(rows):
        y = pad + i * 72 + 50
        d.text((pad, y), label, font=small, fill=scheme.colors["LINE_NUMBERS_COLOR"], anchor="ls")
        d.text((pad + lab_w, y), text, font=roman, fill=scheme.fg, anchor="ls")
        d.text((pad + lab_w + col, y), text, font=italic, fill=scheme.fg, anchor="ls")
    _window(img, scheme).save(out)


def _window(img, scheme):
    """The picture with round corners and a hairline frame, on transparency."""
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), RADIUS, fill=255)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    ImageDraw.Draw(out).rounded_rectangle((0, 0, w - 1, h - 1), RADIUS, outline=scheme.colors["TEARLINE_COLOR"],
                                          width=2)
    return out
