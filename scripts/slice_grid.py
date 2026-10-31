#!/usr/bin/env python3
"""Slice 2x2 watercolor illustration grids into clean transparent square WebP cards.

Pipeline per quadrant: crop -> drop neighbour bleed (border-touching specks) ->
re-centre on a square canvas -> border flood-fill alpha -> feather -> WebP.

  python3 slice_grid.py --grid veggrid1.png \
      --names celery,cucumber,pumpkin,spinach --out assets/img

  python3 slice_grid.py --manifest grids.json --out assets/img
  # grids.json: [{"grid":"a.png","names":["one","two","three","four"]}, ...]
"""
import argparse, json, os, re, sys

import numpy as np
from PIL import Image
from scipy import ndimage

Image.MAX_IMAGE_PIXELS = None


def slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def clean_quadrant(rgb, border_frac=0.32):
    """Return (rgb, alpha) for one quadrant, stripping bleed from neighbours."""
    mx = rgb.min(axis=2)
    spread = rgb.max(axis=2).astype(np.int16) - rgb.min(axis=2).astype(np.int16)
    ink = (mx < 232) | (spread > 18)

    lab, n = ndimage.label(ink, structure=np.ones((3, 3)))
    if n == 0:
        return rgb, np.ones(rgb.shape[:2], np.uint8) * 255

    areas = ndimage.sum(ink, lab, np.arange(1, n + 1))
    biggest = areas.max()
    h, w = ink.shape
    touches = np.zeros(n + 1, bool)
    for edge in (lab[0, :], lab[-1, :], lab[:, 0], lab[:, -1]):
        touches[np.unique(edge)] = True

    keep = np.zeros(n + 1, bool)
    for i in range(1, n + 1):
        # a border-touching fragment far smaller than the subject is neighbour bleed
        if touches[i] and areas[i - 1] < biggest * border_frac:
            continue
        keep[i] = True
    mask = keep[lab]

    ys, xs = np.where(mask)
    if len(ys) < 400:
        return rgb, np.ones(rgb.shape[:2], np.uint8) * 255
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    return rgb[y0:y1 + 1], mask[y0:y1 + 1]


def alpha_matte(rgb, white_floor=242, feather=0.65):
    """Transparent where the paper shows through, judged from the border inward."""
    mx = rgb.min(axis=2)
    near_white = mx >= white_floor
    lab, n = ndimage.label(near_white, structure=np.ones((3, 3)))
    border = np.unique(np.concatenate([lab[0, :], lab[-1, :], lab[:, 0], lab[:, -1]]))
    paper = np.isin(lab, border[border > 0])
    alpha = (~paper).astype(np.float32)
    alpha = ndimage.binary_erosion(alpha, iterations=1).astype(np.float32)
    if feather:
        alpha = ndimage.gaussian_filter(alpha, feather)
    return (np.clip(alpha, 0, 1) * 255).astype(np.uint8)


def place(rgb, alpha, canvas, fit):
    """Scale to `fit` px on its longest side and centre it on a `canvas` canvas."""
    h, w = rgb.shape[:2]
    s = fit / max(h, w)
    nw, nh = max(1, round(w * s)), max(1, round(h * s))
    im = Image.fromarray(rgb).resize((nw, nh), Image.LANCZOS)
    am = Image.fromarray(alpha).resize((nw, nh), Image.LANCZOS)
    out = Image.new('RGBA', (canvas, canvas), (0, 0, 0, 0))
    out.paste(Image.merge('RGBA', (*im.split(), am)), ((canvas - nw) // 2, (canvas - nh) // 2))
    return out


def slice_grid(path, names, out_dir, canvas=512, fit=424, quality=90, margin=0.04):
    im = Image.open(path).convert('RGB')
    W, H = im.size
    mx, my = int(W * margin), int(H * margin)
    made = []
    for i, name in enumerate(names[:4]):
        col, row = i % 2, i // 2
        box = (col * W // 2 + mx, row * H // 2 + my,
               (col + 1) * W // 2 - mx, (row + 1) * H // 2 - my)
        rgb = np.asarray(im.crop(box))
        rgb, mask = clean_quadrant(rgb)
        tile = place(rgb, alpha_matte(rgb), canvas, fit)
        fn = os.path.join(out_dir, slug(name) + '.webp')
        tile.save(fn, 'WEBP', quality=quality, alpha_quality=92, method=6)
        made.append(fn)
    return made


def main():
    ap = argparse.ArgumentParser(description='Slice 2x2 watercolor grids into transparent WebP cards.')
    ap.add_argument('--grid'); ap.add_argument('--names')
    ap.add_argument('--manifest'); ap.add_argument('--out', default='assets/img')
    ap.add_argument('--canvas', type=int, default=512)
    ap.add_argument('--fit', type=int, default=424)
    ap.add_argument('--quality', type=int, default=90)
    a = ap.parse_args()

    jobs = []
    if a.manifest:
        jobs = json.load(open(a.manifest))
    elif a.grid and a.names:
        jobs = [{'grid': a.grid, 'names': a.names.split(',')}]
    if not jobs:
        ap.error('pass --grid + --names, or --manifest')

    os.makedirs(a.out, exist_ok=True)
    total = 0
    for j in jobs:
        if len(j['names']) < 4:
            sys.exit('need 4 names per grid, got %s in %s' % (len(j['names']), j['grid']))
        made = slice_grid(j['grid'], j['names'], a.out, a.canvas, a.fit, a.quality)
        total += len(made)
        print('ok  %-28s -> %s' % (os.path.basename(j['grid']), ', '.join(map(os.path.basename, made))))
    kb = sum(os.path.getsize(os.path.join(a.out, f)) for f in os.listdir(a.out) if f.endswith('.webp'))
    print('done %d tiles in %s (%.0f KB total)' % (total, a.out, kb / 1024))



if __name__ == '__main__':
    main()
