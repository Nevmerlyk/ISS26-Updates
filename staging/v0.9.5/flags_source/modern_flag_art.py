"""Build-time pixel-art references for all 17 replacement national flags.

Drafts approximate official flag geometry at original PS1 flag resolution
64x28. 24x16 and 24x8 are nearest-neighbour *candidates*, not yet the
game's confirmed small-flag UV layouts. Do not promote an image generator
output alone as a game release.
"""
from __future__ import annotations
from math import cos, sin, pi
from typing import Mapping
from PIL import Image, ImageDraw

WIDTH, HEIGHT = 64, 28
COUNTRIES = (
    "cabo_verde", "algeria", "ivory_coast", "ghana", "dr_congo",
    "haiti", "curacao", "jordan", "iraq", "new_zealand",
    "bosnia", "senegal", "canada", "ecuador", "panama",
    "uzbekistan", "qatar",
)
COLORS = {
    "red": "#CE1126", "white": "#FFFFFF", "black": "#000000",
    "yellow": "#FCDC04", "orange": "#FF8200", "blue": "#003893",
    "navy": "#002395", "sky": "#0099B5", "deepgreen": "#006747",
    "maroon": "#8A1538", "gold": "#FFCD00", "nzblue": "#00247D",
    "congoblue": "#007FFF",
}

def _color(text: str) -> str:
    return COLORS.get(text, text)

def _star(draw: ImageDraw.ImageDraw, x: float, y: float, radius: float,
          color: str, points: int = 5) -> None:
    path = []
    for index in range(points*2):
        angle = -pi/2 + index*pi/points
        dist = radius if index % 2 == 0 else radius*0.41
        path.append((x+dist*cos(angle), y+dist*sin(angle)))
    draw.polygon(path, fill=_color(color))

def flag_image(country: str) -> Image.Image:
    if country not in COUNTRIES:
        raise ValueError("Unsupported ISS26 national replacement: " + country)
    im = Image.new("RGB", (WIDTH, HEIGHT), "#FFFFFF")
    d = ImageDraw.Draw(im)
    def rectangle(color, box):
        d.rectangle(tuple(round(v) for v in box), fill=_color(color))
    def polygon(color, shape):
        d.polygon(shape, fill=_color(color))
    def bands(colors, vertical=False, weights=None):
        weights = weights or [1] * len(colors)
        total = sum(weights)
        last = 0
        for c, weight in zip(colors, weights):
            lower = round(last / total * (WIDTH if vertical else HEIGHT))
            last += weight
            upper = round(last / total * (WIDTH if vertical else HEIGHT))
            if vertical:
                rectangle(c, (lower, 0, upper, HEIGHT))
            else:
                rectangle(c, (0, lower, WIDTH, upper))
    if country == "ivory_coast":
        bands(["orange", "white", "deepgreen"], vertical=True)
    elif country == "senegal":
        bands(["deepgreen", "yellow", "red"], vertical=True)
        _star(d, WIDTH/2, HEIGHT/2, 5, "#00853F")
    elif country == "ghana":
        bands(["red", "gold", "deepgreen"])
        _star(d, 32, 14, 5, "black")
    elif country == "cabo_verde":
        bands(["navy", "white", "red", "white", "navy"],
              weights=[6,1,1,1,3])
        for i in range(10):
            angle = -pi/2+i*2*pi/10
            _star(d, 24+7*cos(angle), 18+7*sin(angle), 1.6, "yellow")
    elif country == "algeria":
        bands(["deepgreen", "white"], vertical=True)
        d.ellipse((26,6,44,22), fill="#D21034")
        d.ellipse((30,4,46,20), fill="white")
        _star(d, 41, 13, 4, "#D21034")
    elif country == "bosnia":
        rectangle("navy", (0,0,WIDTH,HEIGHT))
        polygon("yellow", [(35,0), (63,0), (63,27), (58,27)])
        for i in range(9):
            _star(d, 29+i*3.9, i*3.1, 2.2, "white")
    elif country == "dr_congo":
        rectangle("congoblue", (0,0,WIDTH,HEIGHT))
        polygon("gold", [(0,22),(0,28),(8,28),(64,5),(64,0),(58,0)])
        polygon("red", [(0,23),(0,27),(4,27),(64,5),(64,0),(60,0)])
        _star(d, 9, 7, 4, "gold")
    elif country == "haiti":
        bands(["#00209F", "#D21034"])
        rectangle("white", (26,10,38,19))
        polygon("#016A1B", [(28,18),(36,18),(33,12),(31,12)])
        d.line((29,11,35,18), fill="#9B5B28", width=1)
    elif country == "curacao":
        rectangle("navy", (0,0,WIDTH,HEIGHT))
        rectangle("yellow", (0,20,WIDTH,23))
        _star(d,13,7,3,"white")
        _star(d,20,13,2,"white")
    elif country == "jordan":
        bands(["black", "white", "deepgreen"])
        polygon("red", [(0,0),(25,14),(0,28)])
        _star(d,8,14,2,"white",points=7)
    elif country == "iraq":
        bands(["red", "white", "black"])
        d.line((20,14,43,14), fill="#007A3D",width=2)
        for x in (21,28,34,40):
            d.line((x,12,x+2,15), fill="#007A3D",width=1)
    elif country == "new_zealand":
        rectangle("nzblue", (0,0,WIDTH,HEIGHT))
        rectangle("white", (0,0,30,14))
        d.line((0,0,29,13),fill="#C8102E",width=2)
        d.line((0,13,29,0),fill="#C8102E",width=2)
        rectangle("nzblue",(0,5,30,8));rectangle("nzblue",(12,0,17,14))
        rectangle("white",(0,6,30,8));rectangle("white",(13,0,17,14))
        rectangle("red",(0,7,30,8));rectangle("red",(14,0,16,14))
        for x,y in [(43,5),(55,12),(48,22),(38,17)]:
            _star(d,x,y,3,"white");_star(d,x,y,2,"red")
    elif country == "canada":
        bands(["red","white","red"], vertical=True, weights=[1,2,1])
        polygon("red", [(32,4),(35,10),(39,8),(38,12),(42,14),
                        (36,16),(37,20),(33,18),(33,24),(31,24),
                        (31,18),(27,20),(28,16),(22,14),(26,12),
                        (25,8),(29,10)])
    elif country == "ecuador":
        bands(["gold","#0033A0","red"], weights=[2,1,1])
        d.ellipse((28,8,37,18),fill="#8B6220")
        d.ellipse((30,9,35,17),fill="#006A4E")
    elif country == "panama":
        rectangle("white",(0,0,WIDTH,HEIGHT))
        rectangle("red",(32,0,WIDTH,14))
        rectangle("blue",(0,14,32,HEIGHT))
        _star(d,16,7,5,"blue")
        _star(d,48,21,5,"red")
    elif country == "uzbekistan":
        bands(["sky","red","white","red","deepgreen"],
              weights=[6,0.3,5,0.3,6])
        d.ellipse((5,2,13,11),fill="white")
        d.ellipse((8,1,14,9),fill=COLORS["sky"])
        for row,num in enumerate((3,4,5)):
            for col in range(num):
                _star(d,17+3*col,2+3*row,0.95,"white")
    elif country == "qatar":
        rectangle("maroon",(0,0,WIDTH,HEIGHT))
        polygon("white",[(0,0),(24,0)] +
                [(21 if y % 3 else 25,y) for y in range(0,29,2)] +
                [(0,28)])
    return im

def bgr555(pixel: tuple[int,int,int]) -> int:
    r,g,b = pixel
    return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)

def image_bgr555(image: Image.Image) -> tuple[int, ...]:
    if image.mode != "RGB":
        image = image.convert("RGB")
    return tuple(bgr555(pixel) for pixel in image.getdata())

def flag_sizes(country: str) -> Mapping[tuple[int,int], tuple[int,...]]:
    image = flag_image(country)
    return {
        (w,h): image_bgr555(image.resize((w,h),
            Image.Resampling.NEAREST))
        for w,h in ((64,28),(24,16),(24,8))
    }
