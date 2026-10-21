#!/usr/bin/env python3
"""Build the Motif Code release from the sources in this repository.

    python3 build_dist_package.py               fonts, specimen images, archive
    python3 build_dist_package.py --no-images   …without the specimen images
    python3 build_dist_package.py --sync [PATH] first take motiffont/, sources/,
                                                motif.toml, OFL.txt and the colour
                                                scheme from a Microtone checkout
                                                (default ../microtone-js)

Writes
    fonts/variable/   MotifCode[wght].ttf, MotifCode-Italic[wght].ttf
    fonts/ttf/        a static font for every named weight, roman and italic
    fonts/webfonts/   MotifCode-Variable.woff2, MotifCode-Italic-Variable.woff2
    specimen/*.png    the face at work, and every weight
    dist/MotifCode-<version>.zip, what a release attaches

Needs Python 3.11+ and fontTools with brotli; the images need Pillow and
Pygments. Deterministic: the same sources and motif.toml make the same bytes,
the archive included (every date in it is motif.toml's).
"""

import argparse
import os
import shutil
import sys
import tomllib
import zipfile
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from motiffont import assemble, faces  # noqa: E402
from motiffont.assemble import WEIGHTS  # noqa: E402

FAMILY, PS_FAMILY = "Motif Code", "MotifCode"
FONTS, SPECIMEN, DIST = HERE / "fonts", HERE / "specimen", HERE / "dist"

# Microtone is where Motif is made; this repository carries a copy of what
# the code face is built from.
SYNC = {
    "design-system/fonts/motiffont": "motiffont",
    "design-system/fonts/sources": "sources",
    "design-system/fonts/motif.toml": "motif.toml",
    "design-system/fonts/OFL.txt": "OFL.txt",
    "Syntello.v1.icls": "specimen/Syntello.v1.icls",
}

SAMPLES = [
    dict(out="usage-tml.png", file="specimen/samples/huygens_clock.tml", lang="tml", title="Huygens_clock.tml",
         start="// Major triads climbing", end="// A voicing for each", caret=("LADDER", 1)),
    dict(out="usage-python.png", file="motiffont/widths.py", lang="python", title="widths.py",
         start="def matched_weights", end="def fitted_rescale", caret=("target", 1)),
    dict(out="usage-javascript.png", file="specimen/samples/scroll.js", lang="javascript", title="scroll.js",
         start="/**", end=None, caret=("total", 1)),
]
STYLES_TEXT = "fn tile(Mw, il) => [0O, 1lI] ♯♭ 黃"


def load_config():
    with open(HERE / "motif.toml", "rb") as f:
        return tomllib.load(f)


def sync(checkout):
    for src, dst in SYNC.items():
        a, b = checkout / src, HERE / dst
        if not a.exists():
            sys.exit(f"{a} is missing: is {checkout} a Microtone checkout?")
        if a.is_dir():
            shutil.rmtree(b, ignore_errors=True)
            shutil.copytree(a, b, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            b.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(a, b)
        print(f"  synced {dst}")


def style_of(weight, italic):
    """The style name: "Thin", "Regular", "Italic", "Bold Italic"…"""
    label = dict(WEIGHTS)[weight]
    if not italic:
        return label
    return "Italic" if label == "Regular" else f"{label} Italic"


def static_path(weight, italic):
    return FONTS / "ttf" / f"{PS_FAMILY}-{style_of(weight, italic).replace(' ', '')}.ttf"


def name_static(font, weight, italic, version):
    """Name a static instance the way installers group them: Regular, Italic,
    Bold and Bold Italic as one family, every other weight as a family of its
    own (Regular and Italic), and the whole set under one typographic family."""
    style = style_of(weight, italic)
    ribbi = weight in (400, 700)
    family = FAMILY if ribbi else f"{FAMILY} {dict(WEIGHTS)[weight]}"
    sub = ("Bold " if weight == 700 else "") + ("Italic" if italic else "")
    sub = sub.strip() or "Regular"
    ps = f"{PS_FAMILY}-{style.replace(' ', '')}"
    name = font["name"]
    for nid in (1, 2, 3, 4, 6, 16, 17, 25):
        name.removeNames(nameID=nid)
    for nid, s in ((1, family), (2, sub), (3, f"{version};MCTN;{ps}"), (4, f"{FAMILY} {style}"), (6, ps)):
        name.setName(s, nid, 3, 1, 0x409)
    if not ribbi:
        name.setName(FAMILY, 16, 3, 1, 0x409)
        name.setName(style, 17, 3, 1, 0x409)
    os2 = font["OS/2"]
    os2.usWeightClass = weight
    sel = os2.fsSelection & ~(1 | 1 << 5 | 1 << 6)  # ITALIC, BOLD, REGULAR
    sel |= (1 if italic else 0) | (1 << 5 if weight == 700 else 0) | (1 << 6 if sub == "Regular" else 0)
    os2.fsSelection = sel
    font["head"].macStyle = (1 if weight == 700 else 0) | (2 if italic else 0)


def build_fonts(cfg):
    for d in ("variable", "ttf", "webfonts"):
        shutil.rmtree(FONTS / d, ignore_errors=True)
        (FONTS / d).mkdir(parents=True)
    for italic in (False, True):
        stem = PS_FAMILY + ("-Italic" if italic else "")
        vf_path = FONTS / "variable" / f"{stem}[wght].ttf"
        assemble.save(faces.build_code(cfg, HERE / "sources", italic), vf_path,
                      FONTS / "webfonts" / f"{stem}-Variable.woff2")  # no brackets in a URL
        vf = TTFont(vf_path, recalcTimestamp=False)
        for weight, _ in WEIGHTS:
            font = instancer.instantiateVariableFont(vf, {"wght": weight}, static=True)
            name_static(font, weight, italic, cfg["version"])
            font.save(static_path(weight, italic))
        print(f"  {FAMILY}{' Italic' if italic else ''}: {vf_path.relative_to(HERE)} and {len(WEIGHTS)} static weights")


def build_images():
    from PIL import ImageFont

    import specimen
    scheme = specimen.Scheme(SPECIMEN / "Syntello.v1.icls")
    styles = {(bold, italic): ImageFont.truetype(str(static_path(700 if bold else 400, italic)), specimen.SIZE)
              for bold in (False, True) for italic in (False, True)}
    styles["label"] = ImageFont.truetype(str(static_path(400, False)), specimen.LABEL)
    for s in SAMPLES:
        path = HERE / s["file"]
        code = path.read_text()
        runs = specimen.tml_runs(code) if s["lang"] == "tml" else specimen.pygments_runs(code, s["lang"])
        a, b = specimen.excerpt(path, s["start"], s["end"])
        specimen.render_editor(runs, a, b - a, scheme, styles, s["title"], s["caret"], SPECIMEN / s["out"])
        print(f"  specimen/{s['out']}")
    specimen.render_styles([(w, label, static_path(w, False), static_path(w, True)) for w, label in WEIGHTS],
                           scheme, STYLES_TEXT, SPECIMEN / "styles.png")
    print("  specimen/styles.png")


def build_archive(cfg):
    """The release archive: every font, the licence and the README, dated
    with motif.toml's date so that it too is the same bytes every time."""
    DIST.mkdir(exist_ok=True)
    root = f"{PS_FAMILY}-{cfg['version']}"
    out = DIST / f"{root}.zip"
    y, m, d = (int(p) for p in cfg["date"].split("-"))
    files = sorted(p for p in FONTS.rglob("*") if p.is_file()) + [HERE / "OFL.txt", HERE / "README.md"]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files:
            info = zipfile.ZipInfo(f"{root}/{p.relative_to(HERE).as_posix()}", date_time=(y, m, d, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, p.read_bytes(), compresslevel=9)
    print(f"  {out.relative_to(HERE)}: {len(files)} files, {out.stat().st_size} bytes")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--sync", nargs="?", const=str(HERE.parent / "microtone-js"), metavar="PATH",
                    help="the Microtone checkout to refresh the sources from")
    args = ap.parse_args()
    if args.sync:
        sync(Path(args.sync).resolve())
        # motiffont was imported before the sync replaced it: build in a
        # fresh interpreter, or the fonts come from the old code.
        rest = ["--no-images"] if args.no_images else []
        os.execv(sys.executable, [sys.executable, __file__, *rest])
    cfg = load_config()
    build_fonts(cfg)
    if not args.no_images:
        build_images()
    build_archive(cfg)


if __name__ == "__main__":
    main()
