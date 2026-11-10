"""4bpp national-flag palette multiplexing for ISS26 v0.9.5 (research).

The original game has only 28 resident 64x28 national-flag templates for
54 teams. A template may be shared by multiple flags because each national
team has an independent 16-entry PS1 BGR555 palette (index 0 transparent).
This module losslessly combines multiple *desired rendered* flag bitmaps into
one 4bpp template with a different palette for each nation, preserving any
unchanged nations that already use the chosen style.

This is a graphics compiler primitive, NOT a complete patch. Image source
ownership, small-flag sprite UVs, patch application and emulator QA remain
required release gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

FLAG_NATION_INDEX = {
    "cabo_verde": 0, "algeria": 1, "ivory_coast": 3,
    "ghana": 17, "dr_congo": 19, "haiti": 22,
    "curacao": 24, "jordan": 25, "iraq": 26,
    "new_zealand": 27, "bosnia": 30, "senegal": 35,
    "canada": 39, "ecuador": 42, "panama": 43,
    "uzbekistan": 49, "qatar": 51,
}
# Provenance: original clean EU game has free 1,3,10,20,24 after renames.
# Styles 8/11 are shared with existing nations; their rendered flags must be
# provided as protected inputs. SENEGAL remains on its existing style 0.
PROPOSED_STYLE_GROUPS = {
    1: ("algeria", "new_zealand"),
    3: ("dr_congo", "panama"),
    8: ("cabo_verde",),
    10: ("curacao", "ecuador", "uzbekistan"),
    11: ("ivory_coast",),
    20: ("haiti", "bosnia", "canada"),
    24: ("ghana", "jordan", "iraq", "qatar"),
}
PROTECTED_ORIGINAL_FLAG_SLOTS = {
    8: (12, 18, 29),
    11: (23,),
}
COUNTRY_TO_STYLE = {
    country: style for style, countries in PROPOSED_STYLE_GROUPS.items()
    for country in countries
}

@dataclass(frozen=True)
class Multiplex:
    style_id: int
    # One 4bpp index pixel array per supported display size.
    indices_by_size: dict[tuple[int, int], bytes]
    # Each nation gets a complete 16-entry palette, including transparent #0.
    palettes: dict[str, tuple[int, ...]]
    unique_color_tuples: int
    protected_names: tuple[str, ...]

def _valid_image(image: Sequence[int], dimensions: tuple[int, int]) -> None:
    w, h = dimensions
    if w <= 0 or h <= 0 or w % 2 or len(image) != w * h:
        raise ValueError("invalid dimensions or image pixel count")
    if any(not isinstance(c, int) or isinstance(c, bool) or
           not 0 <= c <= 0x7FFF for c in image):
        raise ValueError("PS1 flags must be opaque 15-bit BGR555 colors")

def compile_style(style_id: int,
                  flags: Mapping[str, Mapping[tuple[int, int], Sequence[int]]],
                  protected: Mapping[str, Mapping[tuple[int, int], Sequence[int]]],
                  dimensions: Sequence[tuple[int, int]] =
                  ((64, 28), (24, 16), (24, 8))) -> Multiplex:
    if not 0 <= style_id <= 27:
        raise ValueError("cannot use unverified high style IDs")
    names = tuple(sorted(flags)) + tuple(sorted(protected))
    if not names or len(set(names)) != len(names):
        raise ValueError("duplicate, missing or overlapping team labels")
    dimensions = tuple(dimensions)
    if not dimensions or len(set(dimensions)) != len(dimensions):
        raise ValueError("duplicate/missing dimensions")

    codebook: dict[tuple[int, ...], int] = {}
    indices_by_size: dict[tuple[int, int], bytes] = {}
    for dims in dimensions:
        for name in names:
            if dims not in (flags.get(name) or protected[name]):
                raise ValueError(f"missing {dims} pixels for {name}")
            _valid_image((flags.get(name) or protected[name])[dims], dims)
        out = bytearray()
        for i in range(dims[0] * dims[1]):
            pair = tuple((flags.get(name) or protected[name])[dims][i]
                         for name in names)
            if pair not in codebook:
                if len(codebook) >= 15:
                    raise ValueError(
                        f"style {style_id}: 4bpp atlas would need "
                        f"{len(codebook)+1} opaque entries (maximum 15)")
                codebook[pair] = len(codebook) + 1
            out.append(codebook[pair])
        indices_by_size[dims] = bytes(out)
    palettes = {}
    for c, name in enumerate(names):
        clut = [0] * 16
        for pair, idx in codebook.items():
            clut[idx] = pair[c]
        palettes[name] = tuple(clut)

    result = Multiplex(style_id, indices_by_size, palettes, len(codebook),
                       tuple(sorted(protected)))
    # Byte-for-byte rendering invariants, including every protected team.
    for name in names:
        image_set = flags.get(name) or protected[name]
        for dims in dimensions:
            recovered = tuple(palettes[name][i]
                              for i in indices_by_size[dims])
            if recovered != tuple(image_set[dims]):
                raise AssertionError("round-trip changed a team's flag")
    return result

def pack_4bpp(indices: bytes, dimensions: tuple[int, int]) -> bytes:
    w, h = dimensions
    if w <= 0 or h <= 0 or w % 2 or len(indices) != w * h or (
        any(not 1 <= i <= 15 for i in indices)
    ):
        raise ValueError("bad indexed flag bitmap or transparent pixels")
    return bytes(indices[i] | (indices[i + 1] << 4)
                 for i in range(0, len(indices), 2))

def validate_national_scope(assignments: Mapping[str, int],
                            preserved_style_slots: Mapping[int, Sequence[int]]) -> None:
    expected = set(FLAG_NATION_INDEX) - {"senegal"}
    if set(assignments) != expected:
        raise ValueError("exactly 16 replacement countries required; Senegal is shared")
    if any(assignments[k] != COUNTRY_TO_STYLE[k] for k in expected):
        raise ValueError("unapproved flag-only style plan")
    for style, unaffected in PROTECTED_ORIGINAL_FLAG_SLOTS.items():
        if tuple(preserved_style_slots.get(style, ())) != unaffected:
            raise ValueError("missing protection for unchanged nations")
    if len(FLAG_NATION_INDEX) != 17 or len(expected) != 16:
        raise AssertionError("flag target inventory changed")
