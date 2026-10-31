# Illustration pipeline: 2×2 grids → transparent card art

## Why grids

One ImageGen call per word would cost 24 generations and give 24 slightly different styles.
Asking for a **2×2 grid in one image** pins the style across four words for a quarter of the
cost, because the model paints all four under one style instruction. 24 words = 6 grids.

Grids are consumed and discarded — only the sliced WebPs belong in the project. Keep the raw
grids in `/tmp` so they can be re-sliced with different parameters without re-generating.

ImageGen stamps a small watermark in the bottom-right corner of every output. Whiten that
corner (`W-230, H-70, W, H` → white) before slicing, or it survives in the bottom-right tile.

## Prompt template — A. realistic product photography (default)

```
Use case: product-shot asset sheet
Primary request: A 2x2 grid of four separate photorealistic studio photographs of [CATEGORY],
each in its own quadrant.
Scene/backdrop: seamless pure white (#FFFFFF) studio background, no horizon line, no table edge.
Subjects:
top-left [a soft brown plush teddy bear with a red bow, sitting upright];
top-right [a stack of five colorful painted wooden building blocks];
bottom-left [a classic blue wooden toy train locomotive with a black boiler and red chimney];
bottom-right [a small doll in a yellow dress with brown yarn hair].
Style/medium: photorealistic product photography, 85mm lens, f/8, sharp focus, real materials
(plush fibers, painted wood grain, glossy plastic, matte felt).
Composition/framing: each toy centered inside its own quadrant with generous white margins,
nothing crossing the center lines or touching the edges, each at a natural three-quarter angle.
Lighting/mood: soft even softbox light, bright clean highlights, no cast shadow, no reflection.
Constraints: no text, no labels, no logos, no hands, no props, floating cleanly on pure white,
identical lighting and color grading across all four quadrants.
```

The same non-negotiable clauses apply as for watercolor. Two failure modes are specific to
photorealism:

- **Enclosed background white** — anything that frames a pocket of white (hula hoop, the loop of
  a kite tail, a handle) keeps that white opaque: the flood-fill only walks in from the crop
  border. On a near-white card it is invisible, but `filter: drop-shadow` on the `<img>` renders
  it as a grey slab. The template therefore ships **no drop-shadow on card art**; do not add one.
  If the white patch must go, re-generate the subject without the enclosure.
- **White thin parts vanish** — a white pinwheel stick, a white lanyard, a white balloon string
  is flood-filled away with the background. Ask for colored plastic/hardware ("a bright blue
  plastic stick"), or drop the cord from the prompt entirely.

Slicing is unchanged (`slice_grid.py`); realistic whites sit at 248–254 so the default
`white_floor=242` cuts them cleanly. Contact-sheet the set on a mid-tone background (not white)
— that is the only way enclosed-white and missing-stick defects show up.

## Prompt template — B. watercolor botanical (alternative)

```
Delicate watercolor botanical food illustrations in vintage seed-catalogue style, soft
translucent washes, fine ink detail, muted natural colors, on a clean pure-white background.
A 2x2 grid of four separate [CATEGORY] illustrations:
top-left [a bunch of celery with pale green stalks and leaves];
top-right [a whole green cucumber lying diagonally];
bottom-left [a round orange pumpkin with a brown stem];
bottom-right [a fresh bunch of dark green spinach leaves].
Each [item] centered inside its own quadrant with generous white margins, nothing crossing the
center lines or touching the edges, each shown at a natural three-quarter angle,
no text, no labels, no borders, no shadows, no plates, no hands.
Consistent hand-painted watercolor style across all four.
```

Non-negotiable clauses, each of which maps to a real failure mode:

- **"clean pure-white background"** — `alpha_matte()` flood-fills near-white from the border.
  A cream or textured background yields a solid square instead of a cut-out.
- **"nothing crossing the center lines"** — a subject that straddles a divider loses half its
  silhouette to the neighbouring quadrant. Regenerate rather than try to repair it.
- **"no text, no labels"** — generated labels are unreadable and impossible to crop out cleanly.
- **"no shadows, no plates, no hands"** — cast shadows survive the flood-fill as a grey halo and
  make the card look pasted.
- **"three-quarter angle"** — flat front views look like clipart at 180 px.
- **one colour + one shape cue per subject** — "a round red radish with leafy green tops and a
  slender white root". The model needs the hint to tell radish from beetroot.

Generate at 1024×1024 (square, `size: '1024x1024'`); each quadrant lands at 512 px, which is
exactly the native `--canvas` size, so no resampling happens before the alpha pass.

## Slicing

```bash
python3 scripts/slice_grid.py --grid /tmp/veggrid1.png \
  --names celery,cucumber,pumpkin,spinach --out assets/img

# or queue several grids at once
python3 scripts/slice_grid.py --manifest /tmp/grids.json --out assets/img
# grids.json: [{"grid":"/tmp/veggrid1.png","names":["celery","cucumber","pumpkin","spinach"]}, ...]
```

Output is `assets/img/<slug>.webp`, slug from `--names` (`re.sub(r'[^a-z0-9]+','-')`). Do a
quick pass with `--names` matching the DATA `name` field so `img: 'assets/img/<slug>.webp'`
needs no mapping table.

Four steps, in order — each exists for a reason:

1. **Quadrant crop** (`w/2`, `h/2`).
2. **Bleed removal** — 8-connected `ndimage.label` over the ink mask
   (`min(rgb) < 232` or channel spread `> 18`); any component that touches the crop border and is
   smaller than 32 % of the biggest component is a sliver of the neighbour and gets dropped.
   `border_frac=0.32` is the tuned value: lower leaves watercolor washes from the neighbour,
   higher eats loose leaves and roots of the subject.
3. **Alpha matte** — border flood-fill of pixels `>= white_floor` (242), erode 1 px, Gaussian
   feather 0.65. Feathering is what stops the edges looking die-cut. `white_floor` is the knob
   to raise for pale subjects (cauliflower, turnip) whose interiors approach 242.
4. **Placement + encode** — scale the longest side to `--fit 424`, centre on a `--canvas 512`
   transparent square (≈44 px breathing room on every side), save WebP at `quality 90,
   alpha_quality 92, method 6`. The 44 px pad matters: cards render the image at a fixed box and
   subjects without padding collide with the headword.

## QA before wiring the images in

- Contact-sheet the whole set — `python3 -c` with PIL, or open the folder in Finder. Style drift
  between grids is obvious in a grid of thumbnails and invisible one at a time.
- Check every file has real transparency: `python3 -c "from PIL import Image; im=Image.open(p); print(im.mode, im.getextrema()[3][0])"`.
  A `min alpha` of 255 means the matte failed.
- Check the subject is centred: on a 512 canvas the opaque bbox should sit within roughly
  40–50 px of each edge. Much tighter means bleed removal clipped the subject; much looser means
  the generation ignored the margins.
- Squint test at 180 px (the deck mini size). If the word is only guessable at full size, the
  illustration is not doing its job — regenerate with a more distinctive angle or colour.
