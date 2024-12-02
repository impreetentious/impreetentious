#!/usr/bin/env python3
"""Embed subsetted, open-licensed fonts into the profile SVGs.

The SVGs are rendered by GitHub inside <img>, which blocks external
resources — so fonts must be inlined as data: URIs or they fall back to
whatever the viewer's OS provides. Baskerville and Avenir Next ship only
with macOS, so most visitors previously saw Georgia/Arial: ~11% wider,
which crushed the gap between the headline and the "01" from 91px to 31px.

Lora (OFL) and Inter (OFL) replace them. Both are redistributable, unlike
Apple's system fonts, and Lora's metrics track Baskerville's closely
(headline-to-01 gap of 89px vs 91px), so the layout is preserved.

Only the glyphs actually used are fetched, via the Google Fonts `text=`
parameter, keeping each file small.

Idempotent: re-run after editing any SVG text to refresh the subsets.

    python3 tools/embed-fonts.py
"""

import base64
import pathlib
import re
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SVGS = [
    "assets/banner.svg",
    "assets/portfolio-strip.svg",
]

# Old proprietary stacks -> new embeddable ones. Fallbacks stay as a safety
# net; if embedding ever fails the design degrades instead of breaking.
SERIF_OLD = "Baskerville, 'Iowan Old Style', Georgia, 'Times New Roman', serif"
SANS_OLD = "'Avenir Next', 'Helvetica Neue', Arial, sans-serif"
SERIF_NEW = "Lora, Georgia, serif"
SANS_NEW = "Inter, Arial, sans-serif"

FAMILY = {"serif": "Lora", "sans": "Inter"}
STYLE_TAG = "embedded-fonts"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def faces_used(svg: str):
    """Map every <text> in the SVG to the (kind, weight, style) face it needs,
    and collect the characters each face has to render."""
    used = {}
    for tag, body in re.findall(r"<text([^>]*)>(.*?)</text>", svg, re.S):
        family = re.search(r'font-family="([^"]*)"', tag)
        if not family:
            continue
        kind = "serif" if "Lora" in family.group(1) else "sans"
        weight = re.search(r'font-weight="(\d+)"', tag)
        italic = 'font-style="italic"' in tag
        face = (kind, int(weight.group(1)) if weight else 400, italic)
        text = re.sub(r"<[^>]+>", "", body)
        used.setdefault(face, set()).update(text)
    return used


def fetch_subset(kind: str, weight: int, italic: bool, chars: set) -> bytes:
    """Ask Google Fonts for a woff2 containing only `chars`."""
    axis = f"ital,wght@{1 if italic else 0},{weight}"
    text = "".join(sorted(chars))
    url = (
        "https://fonts.googleapis.com/css2?family="
        + urllib.parse.quote(FAMILY[kind])
        + f":{axis}&text="
        + urllib.parse.quote(text)
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    css = urllib.request.urlopen(req, timeout=30).read().decode()
    match = re.search(r"src:\s*url\(([^)]+)\)\s*format\('woff2'\)", css)
    if not match:
        raise RuntimeError(f"no woff2 for {FAMILY[kind]} {weight} italic={italic}")
    return urllib.request.urlopen(
        urllib.request.Request(match.group(1), headers={"User-Agent": UA}), timeout=30
    ).read()


def build_style(used: dict) -> str:
    rules = []
    for (kind, weight, italic), chars in sorted(used.items(), key=lambda k: str(k[0])):
        woff2 = fetch_subset(kind, weight, italic, chars)
        b64 = base64.b64encode(woff2).decode()
        rules.append(
            f"@font-face{{font-family:'{FAMILY[kind]}';"
            f"font-style:{'italic' if italic else 'normal'};font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2');}}"
        )
        print(f"    {FAMILY[kind]:6} {weight} {'italic' if italic else '      '} "
              f"{len(chars):3} glyphs  {len(woff2)/1024:5.1f} KB")
    return f'  <style id="{STYLE_TAG}">' + "".join(rules) + "</style>\n"


def process(path: pathlib.Path) -> None:
    svg = path.read_text()
    print(f"\n  {path.relative_to(ROOT)}")
    before = len(svg)

    # Strip any previous embed so re-runs don't stack up.
    svg = re.sub(rf'\s*<style id="{STYLE_TAG}">.*?</style>\n?', "\n", svg, flags=re.S)
    svg = svg.replace(SERIF_OLD, SERIF_NEW).replace(SANS_OLD, SANS_NEW)

    used = faces_used(svg)
    if not used:
        print("    no <text> found, skipping")
        return

    style = build_style(used)
    # Insert immediately after the opening <svg ...> tag.
    svg = re.sub(r"(<svg[^>]*>\n)", r"\1" + style, svg, count=1)
    path.write_text(svg)
    print(f"    {before/1024:.1f} KB -> {len(svg)/1024:.1f} KB")


if __name__ == "__main__":
    print("Embedding Lora + Inter (OFL) subsets…")
    for name in SVGS:
        process(ROOT / name)
    print("\nDone. Bump ?v= in README.md so GitHub's camo cache refetches.")
