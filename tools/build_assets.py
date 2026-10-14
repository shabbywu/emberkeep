"""Rebuild the original, hand-drawn 16px atlas. Pillow is a development dependency only."""
from pathlib import Path
import random

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets'
NAMES = ['floor', 'moss', 'wall', 'wall_dark', 'stairs', 'torch', 'hero', 'hero_step',
         'slime', 'slime_step', 'skeleton', 'skeleton_step', 'cultist', 'cultist_cast',
         'warden', 'warden_rage', 'potion', 'chest', 'chest_open', 'sword', 'bolt',
         'whirl', 'shield', 'heart', 'coin', 'skull', 'spark', 'rune', 'banner', 'key',
         'lamp', 'cross']
atlas = Image.new('RGBA', (128, 64))
rng = random.Random(318)


def draw_tile(index):
    im = Image.new('RGBA', (16, 16))
    d = ImageDraw.Draw(im)
    def r(box, color): d.rectangle(box, fill=color)
    def p(x, y, color): d.point((x, y), fill=color)
    ink, stone, top = '#171922', '#34323e', '#53505a'
    gold, pale, red, teal = '#e5b86c', '#ead7ac', '#b95748', '#7ba78d'
    if index in (0, 1):
        r((0, 0, 15, 15), '#2b282f'); r((1, 1, 14, 14), '#302c34')
        r((1, 0, 14, 0), '#3c343e'); r((0, 1, 0, 14), '#24232b')
        for _ in range(7): p(rng.randrange(1, 15), rng.randrange(1, 15), '#37313a')
        if index == 1:
            for box in ((1, 12, 4, 14), (3, 11, 5, 13), (12, 2, 14, 4)):
                r(box, '#394b42')
    elif index in (2, 3):
        r((0, 0, 15, 15), ink)
        for box in ((1, 1, 7, 6), (9, 1, 14, 6), (1, 8, 4, 13), (6, 8, 14, 13)):
            r(box, stone if index == 2 else '#2b2933')
            x, y, xx, _ = box; r((x, y, xx, y), top if index == 2 else '#3a3743')
        r((1, 14, 14, 15), '#211f29'); p(11, 4, '#45414d')
    elif index == 4:
        r((2, 2, 13, 14), ink); r((1, 1, 14, 2), gold)
        for i in range(5):
            r((3+i, 4+i*2, 12-i, 5+i*2), '#70615a')
            r((3+i, 4+i*2, 12-i, 4+i*2), pale)
        p(2, 3, '#bd8c56'); p(13, 3, '#bd8c56')
    elif index in (5, 26, 30):
        if index != 26:
            r((7, 7, 8, 14), '#6b4237'); r((5, 8, 10, 9), gold)
        r((6, 3, 9, 7), '#dc7745'); r((7, 1, 8, 7), '#eeb965')
        r((5, 5, 10, 6), '#d95a3c'); r((7, 4, 8, 6), '#ffe2a0')
        p(8, 0, '#d58752')
    elif index in (6, 7):
        r((4, 6, 11, 13), ink); r((5, 6, 10, 12), red)
        r((3, 8, 4, 11), '#88463e'); r((11, 8, 12, 11), '#d69a6a')
        r((4, 2, 11, 5), '#593e35'); r((5, 3, 10, 6), pale)
        r((4, 1, 10, 2), '#a6754e'); r((4, 2, 6, 4), '#a6754e')
        p(8, 4, ink); p(10, 4, ink)
        r((5, 11, 10, 12), '#d7a55b'); p(8, 11, pale)
        r((5, 13, 6, 14 if index == 6 else 15), '#664b40')
        r((9, 13 if index == 6 else 12, 10, 14), '#664b40')
        r((12, 5, 13, 9), '#c4c1bf'); p(13, 4, pale); r((11, 10, 14, 10), gold)
        r((6, 7, 7, 9), '#df8060')
    elif index in (8, 9):
        dy = 1 if index == 9 else 0
        r((3, 8+dy, 12, 13), '#263a37'); r((2, 10+dy, 13, 12+dy), '#62886b')
        r((4, 7+dy, 11, 12+dy), '#7aa57b'); r((5, 6+dy, 10, 7+dy), '#9ab882')
        p(5, 9+dy, '#202b32'); p(10, 9+dy, '#202b32'); r((7, 11+dy, 8, 11+dy), '#4c6250')
        p(5, 7+dy, '#c4c898')
    elif index in (10, 11, 25):
        r((4, 2, 11, 6), ink); r((5, 1, 10, 6), pale)
        r((4, 3, 11, 5), pale); r((5, 3, 6, 4), ink); r((9, 3, 10, 4), ink)
        p(8, 5, '#806e5c'); r((6, 6, 9, 6), '#a9967a')
        if index != 25:
            r((7, 7, 8, 11), pale)
            for y in (8, 10): r((5, y, 10, y), '#bfae91')
            r((3, 8, 4, 11), pale); r((11, 8, 12, 11), pale)
            r((5, 12, 6, 14), pale); r((9, 12, 10, 15 if index == 11 else 14), pale)
            r((13, 6, 13, 11), '#a8a2a6'); r((12, 12, 14, 12), gold)
    elif index in (12, 13):
        r((5, 2, 10, 13), '#4c3a63'); r((4, 4, 11, 11), '#66507c')
        r((3, 12, 12, 14), '#342e4e'); r((6, 4, 9, 6), ink)
        p(6, 5, '#d9b077'); p(9, 5, '#d9b077'); r((7, 8, 8, 12), '#9c7d92')
        r((13, 4, 13, 14), '#846249'); r((12, 2, 14, 4), '#b589bb')
        if index == 13: p(13, 1, '#f1cdbe'); p(11, 3, '#edbb99'); p(15, 3, '#edbb99')
    elif index in (14, 15):
        r((3, 4, 12, 14), '#242430'); r((4, 4, 11, 12), '#535364')
        r((2, 5, 4, 9), '#717082'); r((11, 5, 13, 9), '#717082')
        r((5, 1, 10, 5), '#656373'); r((4, 0, 5, 2), gold); r((10, 0, 11, 2), gold)
        r((5, 3, 10, 4), ink)
        eye = '#f7b865' if index == 14 else '#ff644a'
        p(6, 3, eye); p(9, 3, eye); r((6, 7, 9, 9), '#423b4a')
        r((7, 7, 8, 8), eye); r((4, 13, 6, 15), '#686270'); r((9, 13, 11, 15), '#686270')
        r((14, 6, 15, 13), '#a4a0a2'); r((13, 13, 15, 14), gold)
    elif index == 16:
        r((6, 2, 9, 4), gold); r((7, 5, 8, 6), '#a8b5b8')
        r((5, 6, 10, 13), '#b74654'); r((4, 8, 11, 11), '#b74654')
        r((6, 7, 7, 10), '#ee9991'); r((5, 12, 10, 13), '#713743')
        r((8, 8, 9, 9), '#dc6870')
    elif index in (17, 18):
        r((2, 7, 13, 13), ink); r((3, 7, 12, 12), '#845b40')
        r((3, 5 if index == 17 else 2, 12, 7), '#b78650')
        r((2, 8, 13, 8), gold); r((7, 8, 8, 10), '#edcc80')
        r((3, 10, 4, 12), '#aa7748'); r((11, 10, 12, 12), '#aa7748')
        if index == 18: r((3, 5, 12, 7), '#211f29')
    elif index == 19:
        d.polygon([(11, 1), (14, 1), (14, 4), (6, 12), (4, 10)], fill='#c5c8c1')
        d.line((6, 10, 13, 3), fill=pale); d.line((3, 8, 8, 13), fill=gold, width=2)
        d.line((5, 11, 2, 14), fill='#9b6647', width=2)
    elif index == 20:
        d.polygon([(8, 1), (3, 8), (7, 8), (5, 15), (13, 6), (8, 6)], fill=gold)
        d.line((8, 3, 5, 7), fill='#fff0be')
    elif index == 21:
        d.arc((2, 2, 13, 13), 25, 320, fill=pale, width=2)
        d.arc((5, 5, 10, 10), 150, 400, fill=gold, width=2)
        d.polygon([(11, 2), (15, 3), (12, 6)], fill=gold)
    elif index == 22:
        d.polygon([(3, 2), (12, 2), (13, 8), (8, 14), (2, 8)], fill='#85818b')
        d.polygon([(4, 3), (11, 3), (11, 8), (8, 11), (4, 8)], fill='#575268')
        r((7, 4, 8, 9), gold)
    elif index == 23:
        d.polygon([(2, 4), (4, 2), (6, 2), (8, 4), (10, 2), (12, 2), (14, 4),
                   (14, 7), (8, 14), (2, 7)], fill='#bf5861')
        r((4, 4, 5, 5), '#eda38e')
    elif index == 24:
        d.ellipse((3, 3, 12, 13), fill='#b78848'); d.ellipse((4, 3, 11, 11), fill=gold)
        r((7, 5, 8, 9), '#896346'); p(5, 5, '#fff0be')
    elif index == 27:
        d.polygon([(8, 1), (14, 8), (8, 14), (1, 8)], outline=gold)
        d.polygon([(8, 4), (11, 8), (8, 11), (4, 8)], outline=red)
    elif index == 28:
        r((2, 0, 3, 15), '#927658'); r((4, 1, 12, 9), red)
        r((4, 2, 11, 3), '#db9c69'); d.polygon([(4, 9), (12, 9), (4, 12)], fill='#843c3d')
    elif index == 29:
        d.ellipse((2, 2, 8, 8), outline=gold, width=2); d.line((7, 7, 13, 13), fill=gold, width=2)
        r((10, 11, 11, 14), gold)
    elif index == 31:
        r((6, 2, 9, 13), teal); r((2, 6, 13, 9), teal)
    return im


def main():
    OUT.mkdir(exist_ok=True)
    for index in range(len(NAMES)):
        atlas.alpha_composite(draw_tile(index), ((index % 8)*16, (index // 8)*16))
    atlas.save(OUT / 'atlas.png')
    print('Built original pixel atlas:', OUT / 'atlas.png')


if __name__ == '__main__':
    main()
