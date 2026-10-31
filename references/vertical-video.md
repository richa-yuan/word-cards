# Vertical video (9:16, Douyin) from the card deck

## Why a second page

`index.html` is interactive: CSS animations, hover states, async TTS. A screen recorder
drifting 2 frames makes the whole clip jitter. `vertical.html` therefore throws the DOM
interaction away and rebuilds the same design as a **deterministic scene**: nothing moves
unless `seek(t)` puts it there, so frame N is identical every time it is captured.

Copy `assets/app-template/vertical.html` next to `index.html` and `assets/data.js`. It is a
complete working scene (intro → N cards → outro); change the copy, the palette and the word
list, keep the timing machinery.

## Scene contract

The renderer only needs three globals:

```js
window.seek = (t) => { /* pure function of time, no CSS animation, no requestAnimationFrame */ };
window.SCENE = { TOTAL, INTRO, DWELL, CARDS_END, N };  // seconds
window.__fit  = () => { /* measure text after fonts load; call before capturing */ };
```

`seek(t)` must be idempotent and clamped (`t = clamp(t, 0, TOTAL)`) — the capture script
calls it once per frame at absolute times, never incrementally.

## Timeline math

```js
const INTRO = 3.4, DWELL = 3.0, FADE_IN = 0.46, FADE_OUT = 0.40;
const CARDS_START = INTRO, CARDS_END = INTRO + N * DWELL;
const OUTRO_LEN = 4.2, TOTAL = CARDS_END + OUTRO_LEN;      // 24 words → 79.6 s
```

Card *i* is driven by `u = t - (INTRO + i*DWELL)` in `[0, DWELL)`. Inside `seekCard(i, u)`:

- `p = easeOutCubic(clamp(u / FADE_IN))` — the card flies from its deck slot to the stage and
  scales from `MINI_W/STAGE.w` to 1. Interpolate the translate as
  `translate((cx-STAGE_CX)*(1-p), (STRIP_CY-STAGE_CY)*(1-p))` so `p = 1` lands exactly centred.
- `qRaw = clamp((u - (DWELL - FADE_OUT)) / FADE_OUT)` — the last 0.4 s is the handoff.
- Reveal ladders stagger in: word 0.06–0.44, IPA 0.16–0.54, rule 0.5–0.8, gloss 0.52–0.88,
  example 0.72–1.06, example gloss 0.86–1.2. Each field is `slot(u, from, to, qRaw)` =
  translateY + opacity, so the card fills while it is held.
- `speaking = u > 0.42 && u < 2.5` drives the speaker pill / waveform, which is what makes the
  silent frame read as "this word is being said".

Deck: 28 slots = `N + PAD*2` (PAD = 2) with **circular clones** —
`idx = ((k - PAD) % N + N) % N`, `offsetFor(i) = i * SLOT`. This is what fixes both bugs you
will otherwise hit: a clamped offset leaves an empty hole at the ends, and the active card sits
off-centre on the first and last word. The lifted card leaves a dashed `.lifted` socket behind so
the gap looks intentional.

Ghosting trap: the mini card and the flying stage card both hold the illustration. Fade
`.m-body` by `held / 0.5` where `held = Math.min(p, 1 - clamp((qRaw - 0.45) / 0.55))`, and ramp
the stage card with `opacity = clamp(u/0.14) * (1-qRaw)`.

## Douyin layout and safe zones

Canvas 1080×1920. Douyin overlays its own chrome: the caption/description block covers roughly
the bottom 300 px and the right rail (~150 px) holds the avatar, like and share buttons. Put
nothing load-bearing there.

```js
const STAGE = { left: 62, top: 300, w: 956, h: 846 };   // word card, centred at (540, 723)
const SLOT = 200, STRIP_LEFT = 50, STRIP_TOP = 1318;    // deck, 180 px cards
.footer top: 1688px                                     // 30 px of text only, decorative
```

## Visual system

The default look is a "toy box" flashcard: pure-white card, 3 px ink border (`#12151c`), a solid
accent slab under the card (`0 16px 0 -6px var(--acc)`), and one accent colour per card so every
frame reads differently without moving any layout.

```js
const ACCENTS = [ {c:'#ff4b5c', s:'rgba(255,75,92,.16)'},   // coral
                  {c:'#ffa21f', s:'rgba(255,162,31,.20)'},  // amber
                  {c:'#00b39b', s:'rgba(0,179,155,.16)'},   // teal
                  {c:'#2d6bff', s:'rgba(45,107,255,.14)'},  // blue
                  {c:'#9b51e0', s:'rgba(155,81,224,.16)'} ];// violet
```

Set `--acc` / `--acc-soft` on `#frame` inside `setContent(i)`; the card slab, number pill,
speaker pill, rule, active mini card and active tick all inherit them. Background is a warm→cool
pastel gradient with a masked dot grid (no film-grain overlay — it fights photoreal art).

**Opening carries no word count.** The big title is just the theme (「玩具单词」), the brand pill
says `Toy Box · Play & Learn` without `24 Words`, and the whole `.meter` block (ticks + `00 / 24`)
is hidden for the entire intro — `meterEl.style.opacity = '0'` in `seekIntro`, back to `'1'` in
`seekCard`. The outro drops the count too.

Sizes that survived review: word 96 px Nunito 900 on a marker-swipe highlight, Chinese gloss
58 px weight 800, IPA 34 px, example 33 px, example gloss 26 px, art 348 px with **no
`drop-shadow`** (realistic cut-outs carry enclosed white that a shadow would expose). The card is
846 px tall; with these numbers English + Chinese example both fit with ~55 px of breathing room
at the bottom — check every frame for a card whose example wraps to two lines.

Tall subjects (a block tower) look narrow because `object-fit: contain` fits the long side; that
is fine, do not zoom per-image.

## Pipeline

Serve the folder over HTTP (file:// blocks the font/module loads the capture script relies on):

```bash
python3 -m http.server 4317 --bind 127.0.0.1
```

**1. Sanity check the scene** — eyeball five frames before burning a full capture:

```bash
node scripts/render_frames.cjs --url http://127.0.0.1:4317/vertical.html \
  --out /tmp/vcheck --preview 0.5,1.8,3.6,40,78
```

**2. Capture every frame.** 30 fps × 79.6 s ≈ 2 400 JPEGs; takes a few minutes.

```bash
node scripts/render_frames.cjs --url http://127.0.0.1:4317/vertical.html \
  --out /tmp/frames --fps 30 --size 1080x1920 --q 92
```

It waits for `document.fonts.ready` and every image, calls `__fit()`, reads `SCENE.TOTAL`,
and prints console/network problems — fix those before encoding, they show up as blank text.

**3. Voice track.** Edge neural voices by default (`build_audio_neural.py`), same timeline, same
tap clicks, far more natural than `say` — the difference is obvious on a kids' clip:

```bash
python3 scripts/build_audio_neural.py --data assets/data.js --out /tmp/track.wav \
  --outro-text "玩具单词，全部打卡。"
```

It renders all clips concurrently, trims leading/trailing silence so each word starts exactly on
its beat, and prints the per-card slot table. Needs network; offline fallback is the original
`build_audio.py` (`macOS say`, deterministic but flatter).

**4. Encode:**

```bash
bash scripts/encode.sh /tmp/frames /tmp/track.wav "单词卡-抖音竖屏-1080x1920.mp4" 30 1080x1920
```

## Encode spec (why each flag)

JPEG inputs are full-range, which silently tags the file `yuvj420p` and makes Douyin
re-transcode it into washed-out blacks. Force the conversion:

```
-vf scale=1080:1920:in_range=full:out_range=limited:flags=lanczos,format=yuv420p
-c:v libx264 -preset slow -crf 17 -profile:v high -level 4.0
-color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709
-pix_fmt yuv420p -c:a aac -b:a 192k -ar 44100 -ac 2 -shortest -movflags +faststart
```

Verify with `ffprobe -v error -show_streams`: expect `yuv420p(tv, bt709/unknown/unknown)`,
`h264 (High)`, 30 fps, AAC LC 44100 stereo. `encode.sh` prints these lines itself.

## Audio budget — the constraint that decides the pacing

`DWELL` is not a taste choice, it is set by how long the voice takes. With 3.0 s per card the
measured slot is 2.12–2.62 s (word + Chinese gloss, neural voice), which leaves ~0.4–0.9 s of air.
The English
example sentence is **on screen but un-narrated** — reading it needs 4.5–5 s per card, i.e. a
90–120 s video for 24 words. If the user wants the sentences spoken, raise `DWELL` in
`vertical.html` **and** pass the same value to `build_audio.py --dwell`, then re-capture; the
frame count and every `SCENE` number follow from that one constant.

`build_audio.py` warns per card when a slot exceeds `dwell - 0.25`; treat those warnings as the
go/no-go for the current pacing. There is no BGM in the delivered clip because no licensed
source existed locally — ask before adding a track, and duck it ~12 dB under the voice.
