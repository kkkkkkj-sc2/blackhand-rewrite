#!/usr/bin/env python3
"""Render original copper/charcoal artwork for the Egun victory screen."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from png2windds import convert

ROOT = Path(__file__).resolve().parent.parent


def main():
    scale = 3
    image = Image.new('RGB', (732 * scale, 376 * scale), '#080909')
    draw = ImageDraw.Draw(image)

    def polygon(points, fill):
        draw.polygon([(x * scale, y * scale) for x, y in points], fill=fill)

    # Receding alley and shuttered windows, drawn without third-party assets.
    polygon([(0, 0), (234, 68), (279, 282), (0, 376)], '#161313')
    polygon([(732, 0), (498, 68), (453, 282), (732, 376)], '#171414')
    for row in range(3):
        y = 52 + row * 59
        polygon([(54, y), (103, y + 9), (110, y + 37), (60, y + 29)], '#35271f')
        polygon([(678, y), (629, y + 9), (622, y + 37), (672, y + 29)], '#35271f')

    # Worn copper badge and a clenched fist, rather than a weapon or a killer.
    draw.ellipse((270 * scale, 24 * scale, 462 * scale, 216 * scale), outline='#6e4932', width=2 * scale)
    draw.ellipse((278 * scale, 32 * scale, 454 * scale, 208 * scale), outline='#30251f', width=scale)
    polygon([(328, 173), (316, 135), (309, 106), (320, 93), (336, 100),
             (335, 74), (347, 65), (360, 71), (367, 60), (381, 65),
             (391, 61), (404, 71), (411, 71), (423, 84), (424, 122),
             (405, 155), (398, 184), (343, 184)], '#c47a44')
    polygon([(328, 173), (343, 184), (398, 184), (405, 155),
             (382, 160), (364, 143), (339, 147)], '#8f5434')
    for x, y in ((351, 79), (373, 76), (395, 77), (414, 87)):
        draw.line((x * scale, y * scale, (x + 2) * scale, (y + 34) * scale), fill='#623f2d', width=2 * scale)
    draw.line((324 * scale, 111 * scale, 350 * scale, 132 * scale, 381 * scale, 127 * scale), fill='#623f2d', width=2 * scale)

    chinese = ImageFont.truetype('/usr/share/fonts/noto-cjk/NotoSerifCJK-Bold.ttc', 59 * scale)
    latin = ImageFont.truetype('/usr/share/fonts/liberation/LiberationSans-Regular.ttf', 15 * scale)
    draw.text((366 * scale, 218 * scale), '恶 棍', font=chinese, anchor='mt', fill='#c47a44')
    draw.text((366 * scale, 316 * scale), 'V I C T O R Y', font=latin, anchor='mt', fill='#bba28a')
    draw.line((232 * scale, 300 * scale, 500 * scale, 300 * scale), fill='#6e4932', width=scale)

    image = image.resize((732, 376), Image.Resampling.LANCZOS)
    png, dds = ROOT / 'data/WinEgun.png', ROOT / 'data/WinEgun.dds'
    image.save(png)
    print(f'{png.name} -> {dds.name}: {convert(png, dds)} bytes (BGR)')


if __name__ == '__main__':
    main()
