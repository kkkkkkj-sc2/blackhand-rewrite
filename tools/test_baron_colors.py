#!/usr/bin/env python3
"""Check leader/recruit palette wiring; not an SC2 rendering test."""
from pathlib import Path
import re

from test_egun import function

ROOT = Path(__file__).resolve().parent.parent


def colors(percentages):
    return ''.join(f'{round(channel * 255 / 100):02X}' for channel in percentages)


def contrast_on_black(hex_color):
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
              for value in channels]
    return (sum(weight * value for weight, value in zip((0.2126, 0.7152, 0.0722), linear)) + 0.05) / 0.05


def main():
    entries = {}
    for name in ('strings-baron.txt', 'strings-faction.txt'):
        for line in (ROOT / 'work/blackhand' / name).read_text().splitlines():
            if line.startswith('Param/Value/'):
                key, value = line.split('=', 1)
                entries[key] = value

    source = (ROOT / 'work/blackhand/CustomLogic.galaxy').read_text()
    assert entries['Param/Value/NJNAME'] == '<c val="C96B78">男爵</c>'
    assert entries['Param/Value/NJTAG'] == ' (<c val="C96B78">领袖</c>)'
    assert entries['Param/Value/TDNAME'] == '<c val="3366FF">泰斗</c>'
    assert entries['Param/Value/BHFJOIN2'] == '你转变为「<c val="D9A08F">黑手党</c>」阵营。'
    assert entries['Param/Value/BHFJOIN5'] == '你转变为「<c val="3366FF">三合会</c>」阵营。'
    for key, value in entries.items():
        if key.startswith('Param/Value/BHFROLE'):
            assert '<c' not in value, 'profession text must not override its alignment palette'

    name = function(source, 'gf_BHRoleName')
    palette = re.findall(r'Color\(([\d.]+), ([\d.]+), ([\d.]+)\)', name)
    assert len(palette) == 2
    assert colors(tuple(map(float, palette[0]))) == 'D9A08F'
    assert colors(tuple(map(float, palette[1]))) == '3366FF'
    assert 'Color(78.82, 41.96, 47.06)' in function(source, 'gf_BRDraw')
    assert colors((78.82, 41.96, 47.06)) == 'C96B78'
    for color in ('C96B78', 'D9A08F'):
        contrast = contrast_on_black(color)
        assert contrast >= 4.5
        print(f'PASS {color}: numeric sRGB contrast on black {contrast:.2f}:1')

    print('PASS: distinct soft Baron/recruit palettes; names, badge, buttons and join message wired; Triad unchanged')


if __name__ == '__main__':
    main()
