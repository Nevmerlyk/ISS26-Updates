#!/usr/bin/env python3
"""Prepare authentic 2026/27 club crests for ISS26 graphics.

Input vector files come from a third-party football-logo collection.
No copyrighted game image, BIN or CUE is read or bundled.
Run on GitHub Actions; output both source-rendered previews and deterministic
indexed (16-colour) pixel-art sprites for PS1 graphical integration.
"""
from __future__ import annotations
import csv
import io
import json
import pathlib
import hashlib
import struct
import urllib.parse
import urllib.request

import cairosvg
from PIL import Image

SOURCE_REPO = "JoseArroyave/football-logos"
SOURCE_REF = "5ab11fed47427b3003f4b276554491fe683387b1"
CLUBS = (
    (0, "SHK", "Shakhtar", "logos/ukraine/Shakhtar.svg"),
    (1, "KRY", "FC Kryvbass", "logos/ukraine/Kryvbas.svg"),
    (2, "LEV", "Leverkusen", "logos/germany/Bayer_Leverkusen.svg"),
    (3, "AJX", "Ajax", "logos/netherlands/Ajax.svg"),
    (4, "NEW", "Newcastle United", "logos/england/Newcastle_United.svg"),
    (5, "SCP", "Sporting CP", "logos/portugal/Sporting_CP.svg"),
    (6, "BEN", "Benfica", "logos/portugal/Benfica.svg"),
    (7, "ROM", "Roma", "logos/italy/AS_Roma.svg"),
    (8, "BAY", "Bayern", "logos/germany/Bayern_Munich.svg"),
    (9, "ACM", "AC Milan", "logos/italy/Milan.svg"),
    (10, "JUV", "Juventus", "logos/italy/Juventus.svg"),
    (11, "INT", "Inter Milan", "logos/italy/Inter.svg"),
    (12, "BVB", "Dortmund", "logos/germany/Borussia_Dortmund.svg"),
    (13, "ATM", "Atletico", "logos/spain/Atletico_Madrid.svg"),
    (14, "NAP", "Napoli", "logos/italy/Napoli.svg"),
    (15, "RMA", "Real Madrid", "logos/spain/Real_Madrid.svg"),
    (16, "PSG", "PSG", "logos/france/PSG.svg"),
    (17, "BAR", "Barcelona", "logos/spain/Barcelona.svg"),
    (18, "TOT", "Tottenham", "logos/england/Tottenham.svg"),
    (19, "MCI", "Manchester City", "logos/england/Manchester_City.svg"),
    (20, "LIV", "Liverpool", "logos/england/Liverpool_FC.svg"),
    (21, "CHE", "Chelsea", "logos/england/Chelsea.svg"),
    (22, "ARS", "Arsenal", "logos/england/Arsenal.svg"),
    (23, "MUN", "Manchester United", "logos/england/Manchester_United.svg"),
)
SIZES = ((64, 28), (24, 16), (24, 8))


def fit_image(image: Image.Image, width: int, height: int) -> Image.Image:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        raise ValueError("Transparent source has no visible crest")
    image = image.crop(bbox)
    image.thumbnail((width, height), Image.Resampling.LANCZOS)
    result = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    result.alpha_composite(image, ((width - image.width) // 2,
                                   (height - image.height) // 2))
    return result


def indexed_4bpp(image: Image.Image) -> tuple[bytes, list[list[int]], list[tuple[int,int,int]]]:
    # Index 0 is transparent: do not let the reducer allocate opaque black there.
    rgb = image.convert("RGB")
    alpha = image.getchannel("A")
    pix = [(x, y) for y in range(image.height) for x in range(image.width)
           if alpha.getpixel((x, y)) >= 112]
    if not pix:
        raise ValueError("Logo too small for PS1 format")
    sample = Image.new("RGB", (len(pix), 1))
    sample.putdata([rgb.getpixel(pos) for pos in pix])
    pal = sample.quantize(colors=14, method=Image.Quantize.MEDIANCUT)
    colors = []
    for i in range(14):
        raw = (pal.getpalette() or [])[3*i:3*i+3]
        colors.append(tuple(raw) if len(raw)==3 else (0, 0, 0))
    colors.append((255,255,255))  # index 15 reserved for white stadium backing
    opaque_image = Image.new("RGB", image.size)
    opaque_image.paste(rgb)
    # Colors are mapped explicitly; unused palette entries remain black.
    # Re-map RGB to exact authored palette so output is stable and transparent.
    indices = []
    for y in range(image.height):
        row = []
        for x in range(image.width):
            if alpha.getpixel((x,y)) < 112:
                row.append(0)
            else:
                v = rgb.getpixel((x,y))
                j = min(range(14), key=lambda k: sum((v[t]-colors[k][t])**2 for t in range(3)))
                row.append(j + 1)
        indices.append(row)
    # Screenshot-ready RGBA preview.
    output = Image.new("RGBA", image.size)
    output.putdata([(0,0,0,0) if c==0 else (*colors[c-1],255)
                    for row in indices for c in row])
    buf = io.BytesIO()
    output.save(buf, format="PNG")
    return buf.getvalue(), indices, [(0,0,0)] + colors



def pack_4bpp(rows: list[list[int]], width: int, height: int) -> bytes:
    """PS1 indexed texture: low nibble is left pixel; 0 remains transparent."""
    if width % 2 or len(rows) != height or any(len(row) != width for row in rows):
        raise ValueError("Malformed 4bpp texture")
    flat = [v for row in rows for v in row]
    if any(type(v) is not int or not 0 <= v <= 15 for v in flat):
        raise ValueError("Palette index out of bounds")
    packed = bytes(flat[i] | (flat[i+1] << 4) for i in range(0,len(flat),2))
    if len(packed) != width*height//2:
        raise AssertionError("Bad texture length")
    return packed


def bgr555_clut(palette: list[tuple[int,int,int]]) -> bytes:
    """16 PS1 BGR555 entries, palette index 0 reserved as transparent."""
    if len(palette) != 16:
        raise ValueError("16-entry 4bpp palette required")
    words=[]
    for r,g,b in palette:
        if not all(0 <= v <= 255 for v in (r,g,b)):
            raise ValueError("RGB channel out of bounds")
        words.append(((b*31+127)//255 << 10) |
                     ((g*31+127)//255 << 5) | ((r*31+127)//255))
    result=struct.pack("<16H",*words)
    assert len(result)==32
    return result

def main():
    root = pathlib.Path("dist/iss26-artwork/club-crests")
    root.mkdir(parents=True, exist_ok=True)
    catalog = []
    for index, code, name, source in CLUBS:
        url = ("https://raw.githubusercontent.com/" + SOURCE_REPO
               + "/" + SOURCE_REF + "/" + "/".join(
                   urllib.parse.quote(bit, safe="()") for bit in source.split("/")))
        req = urllib.request.Request(url, headers={"User-Agent":"ISS26-Graphics-Builder"})
        try:
            with urllib.request.urlopen(req, timeout=40) as res:
                svg = res.read()
            png = cairosvg.svg2png(bytestring=svg, output_width=320, output_height=320)
            image = Image.open(io.BytesIO(png)).convert("RGBA")
            image = fit_image(image, 128, 128)
            image.save(root / f"{index:02d}_{code}_reference.png")
            entries={}
            for w,h in SIZES:
                small=fit_image(image,w,h)
                data,indices,palette=indexed_4bpp(small)
                texture=pack_4bpp(indices,w,h)
                clut=bgr555_clut(palette)
                stem=f"{index:02d}_{code}_{w}x{h}"
                (root/f"{stem}.png").write_bytes(data)
                (root/f"{stem}.4bpp").write_bytes(texture)
                (root/f"{stem}.clut").write_bytes(clut)
                assert len(texture)==w*h//2 and len(clut)==32
                entries[f"{w}x{h}"]={"width":w,"height":h,
                    "texture_sha256":hashlib.sha256(texture).hexdigest(),
                    "clut_sha256":hashlib.sha256(clut).hexdigest(),
                    "image_sha256":hashlib.sha256(data).hexdigest()}
            catalog.append({"slot":index,"code":code,"name":name,
                "source_url":url,"palette_rgb":palette,
                "sizes":entries})
            print(f"Created accurate crest source and PS1 sprite for {code}")
        except Exception as exc:
            raise RuntimeError(f"Cannot validate crest source {code}: {url}") from exc
    (root.parent/"clubs.json").write_text(json.dumps(catalog,ensure_ascii=False,indent=2),
                                            encoding="utf-8")
    assert len(catalog)==24 and [r["slot"] for r in catalog]==list(range(24))
    print("PASS: 24 exact active club identities; 72 4bpp 3-size sprites + 32-byte CLUTs. SOURCE ART ONLY: no runtime disc integration.")

if __name__=="__main__":
    main()
