#!/usr/bin/env python3
"""Generate the night edition: dark-theme twins of each profile SVG.

GitHub picks between them with <picture media="(prefers-color-scheme: dark)">,
so the light files stay untouched and this only adds *-night.svg alongside.

Colours are remapped in a single pass — sequential replaces would collide,
since ink (#1C1814) becomes page cream and page cream becomes ink. The dark
slabs (the portfolio strip, the card CTA bars) invert to cream, which keeps
the light edition's rhythm: that block is always the one that pops.

Run after embed-fonts.py; the base64 font blocks are copied through
untouched (base64 has no '#', so the colour regex can't corrupt them).

    python3 tools/make-night.py
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SVGS = [
    "assets/banner.svg",
    "assets/portfolio-strip.svg",
    "assets/projects/nexus-iq.svg",
    "assets/projects/wind-tunnel.svg",
    "assets/projects/gt-sandbox.svg",
]

# light -> night. Verified for WCAG AA against the night page colour (#14110E):
#   F2E8D5 15.5:1 · CBBEAA 10.3:1 · 8A7E70 4.7:1 · C9603C 4.7:1
NIGHT = {
    "F2E8D5": "14110E",  # page cream        -> near-black (warm)
    "1C1814": "F2E8D5",  # ink               -> cream (text, borders, inverted slabs)
    "342C26": "CBBEAA",  # body copy         -> warm light grey
    "6E6256": "8A7E70",  # muted label       -> lifted muted
    "CBBEAA": "6E6256",  # subtext on a slab -> muted dark (slab is now cream)
    "A5482D": "C9603C",  # rust accent       -> brightened for dark ground
}

PATTERN = re.compile("#(" + "|".join(NIGHT) + ")", re.IGNORECASE)


def to_night(svg: str) -> str:
    # Single pass: every match is resolved against the original text, so the
    # cream<->ink swap can't feed back on itself.
    return PATTERN.sub(lambda m: "#" + NIGHT[m.group(1).upper()], svg)


def main() -> None:
    print("Building night edition…")
    for name in SVGS:
        src = ROOT / name
        dst = src.with_name(src.stem + "-night" + src.suffix)
        svg = src.read_text()

        night = to_night(svg)
        if night == svg:
            print(f"  !! {name}: no colours remapped — check the palette")
            sys.exit(1)

        # Keep the accessible name honest; these are the same artwork at night.
        night = night.replace("<title id=\"title\">", "<title id=\"title\">Night edition — ", 1)
        dst.write_text(night)

        swaps = len(PATTERN.findall(svg))
        print(f"  {dst.relative_to(ROOT)}  ({swaps} colours remapped, {len(night)/1024:.1f} KB)")

    print("\nDone. README needs <picture> + a ?v= bump.")


if __name__ == "__main__":
    main()
