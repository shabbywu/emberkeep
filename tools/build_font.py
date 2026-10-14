"""Subset an OFL Noto Sans SC source font to the shipped game's own text."""
import argparse
from pathlib import Path
from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    characters = set(chr(i) for i in range(32, 127))
    characters.update('×−→↗·Ⅱ✦！？，。；：、（）【】「」《》…—灯火地牢旅人守墓者')
    for folder in (ROOT/'game', ROOT/'assets'):
        for path in folder.rglob('*'):
            if path.suffix in ('.py', '.html', '.js', '.css'):
                characters.update(path.read_text(encoding='utf-8'))
    characters.update((ROOT/'run.py').read_text(encoding='utf-8'))
    font = TTFont(args.source)
    if 'fvar' in font:
        font = instantiateVariableFont(font, {'wght': 400}, inplace=True)
    options = subset.Options()
    options.name_IDs = ['*']
    options.name_legacy = True
    options.name_languages = ['*']
    worker = subset.Subsetter(options)
    worker.populate(unicodes=[ord(c) for c in characters])
    worker.subset(font)
    font.flavor = 'woff2'
    font.save(ROOT/'assets'/'ember.woff2')
    print('Built Noto Sans SC subset:', (ROOT/'assets'/'ember.woff2').stat().st_size, 'bytes')


if __name__ == '__main__':
    main()
