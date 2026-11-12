#!/usr/bin/env python3
"""ISS26 v0.9.5: safely lay out Cape Verde within two fixed prematch sprites.

Test12 verified screen rectangles: (24,38,128,16) and (152,38,88,16).
They TOUCH. The observed 72px gap is ink/transparent bitmap spacing, not a
screen rectangle gap. Caller must supply the verified original Test13 Verde
raster and a verified replacement Cape glyph raster. No disc files edited.
"""
from dataclasses import dataclass

LEFT,RIGHT,H=128,88,16

@dataclass(frozen=True)
class BBox:
    x:int
    y:int
    w:int
    h:int

def pixel(data:bytes,w:int,x:int,y:int)->int:
    if not 0<=x<w or not 0<=y<H: raise ValueError("pixel out of range")
    return (data[y*w//2+x//2]>>(4*(x%2)))&15

def set_pixel(data:bytearray,w:int,x:int,y:int,value:int):
    if not 0<=value<16 or not 0<=x<w or not 0<=y<H:
        raise ValueError("bad 4bpp pixel")
    n=y*w//2+x//2
    shift=4*(x%2)
    data[n]=(data[n]&~(15<<shift))|(value<<shift)

def ink_bbox(data:bytes,w:int)->BBox|None:
    if not w or w%2 or len(data)!=w*H//2:
        raise ValueError("invalid 4bpp sprite")
    coords=[(x,y) for y in range(H) for x in range(w) if pixel(data,w,x,y)]
    if not coords:return None
    lo_x=min(x for x,y in coords);hi_x=max(x for x,y in coords)
    lo_y=min(y for x,y in coords);hi_y=max(y for x,y in coords)
    return BBox(lo_x,lo_y,hi_x-lo_x+1,hi_y-lo_y+1)

def recompose(cape:bytes,cape_width:int,verde:bytes,*,space_px:int=7,
              cape_left:int=2,cape_top:int=2,verde_y:int|None=None):
    """Return unchanged-size (128x16,88x16) indexed sprites and layout audit.

    Does not generate the lettering itself. Does not certify source UV/CLUT.
    Raster pixels outside those exact two source sprite rectangles must be
    kept unmodified by whichever patch builder uses these outputs.
    """
    if len(verde)!=RIGHT*H//2 or not 4<=space_px<=12:
        raise ValueError("invalid Verde raster or word spacing")
    cb=ink_bbox(cape,cape_width);vb=ink_bbox(verde,RIGHT)
    if cb is None or vb is None:
        raise ValueError("empty word raster")
    if cape_top<0 or cape_top+cb.h>H or cape_left<0:
        raise ValueError("Cape vertical or left bounds")
    if verde_y is None:verde_y=vb.y
    if verde_y<0 or verde_y+vb.h>H:
        raise ValueError("Verde vertical bounds")
    verde_x=cape_left+cb.w+space_px
    width=LEFT+RIGHT
    if verde_x+vb.w>width:
        raise ValueError("Cape Verde exceeds unchanged draw rectangles")
    merged=bytearray(width*H//2)
    for y in range(cb.h):
        for x in range(cb.w):
            c=pixel(cape,cape_width,cb.x+x,cb.y+y)
            if c:set_pixel(merged,width,cape_left+x,cape_top+y,c)
    for y in range(vb.h):
        for x in range(vb.w):
            c=pixel(verde,RIGHT,vb.x+x,vb.y+y)
            if c:set_pixel(merged,width,verde_x+x,verde_y+y,c)
    a=bytearray(LEFT*H//2);b=bytearray(RIGHT*H//2)
    for y in range(H):
        off=y*(width//2)
        a[y*LEFT//2:(y+1)*LEFT//2]=merged[off:off+LEFT//2]
        b[y*RIGHT//2:(y+1)*RIGHT//2]=merged[off+LEFT//2:off+width//2]
    return bytes(a),bytes(b),{
        "screen_draw_x":[24,152],
        "rectangles_touch":True,
        "first_ink_screen_x":24+cape_left,
        "last_ink_screen_x":24+verde_x+vb.w-1,
        "cape_ink_width":cb.w,"verde_ink_width":vb.w,
        "visible_word_gap_px":space_px,
        "second_sprite_nonempty":any(b),
        "draw_positions_modified":False,
        "verified_cape_artwork":False,
    }
