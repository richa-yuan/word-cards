# The card app (index.html)

Zero-build static site: `index.html` + `assets/data.js` + `assets/img/*.webp` +
`assets/fonts/*.woff2`. Works over `http://` and `file://` with no network
calls. Copy `assets/app-template/` into the project and rewrite `assets/data.js`.

## Data schema

One entry per card, array order = grid order (row-major):

```js
const DATA = [
  { name:'celery', ipa:'/ˈseləri/', zh:'芹菜',
    example:'Celery stays crisp in cold water.', exampleZh:'芹菜泡在冷水里能保持爽脆。',
    img:'assets/img/celery.webp' },
];
```

`name` is what gets spoken, so use the everyday form (`bell pepper`, not
`capsicum`). `img` is the slug of `name`: lowercase, spaces -> hyphens
(`sweet potato` -> `sweet-potato.webp`). Top-level `const DATA` in a classic
`<script>` is visible to later scripts, which is how `index.html` and
`vertical.html` share one file.

## Layout

| viewport | grid | modal |
|---|---|---|
| >= 901px | 4 columns | two columns (art left, text right), `min(880px,100%)` |
| 721-900px | 3 columns | two columns |
| <= 720px | 2 columns | stacked, `max-height: calc(100dvh - 40px)` |

Breakpoints for the modal are at 880px, not 720px — the two-column modal needs
more width than the grid does. Always write `max-height: calc(100vh - 40px)`
*before* the `100dvh` line so older Safari keeps a fallback.

## Pronunciation (Web Speech API)

```js
const u = new SpeechSynthesisUtterance(text);
u.lang = 'en-US'; u.rate = 0.9;
const v = pickVoice(); if (v) u.voice = v;      // getVoices() is async
```

Three traps that cost real debugging time:

1. **`getVoices()` returns `[]` at first call.** Populate on `voiceschanged`
   and re-pick lazily at speak time, never at load time.
2. **Stale audio after navigation.** `speechSynthesis.cancel()` does not always
   stop a queued utterance before its `onstart`. Guard every callback with a
   token: `const token = ++speakToken;` then `if (token === speakToken)` inside
   `onstart`/`onend`/`onerror`, and bump `speakToken` in `stopSpeech()`.
3. **Chrome ignores `speak()` without a gesture.** Re-issue it inside a short
   `setTimeout` after the open animation, and keep an explicit speaker button
   so a blocked first utterance is recoverable.

Persist the auto-speak toggle in `localStorage` inside `try {} catch {}` — it
throws in some sandboxed contexts and in `file://` on certain configs.

## Open/close motion (FLIP)

Measure the clicked card, then animate the modal *from* that rect *to* its own:

```js
const sr = src.getBoundingClientRect(), pr = modal.getBoundingClientRect();
modal.animate([
  { transform:`translate(${dx}px, ${dy}px) scale(${sx}, ${sy})`, opacity:.5 },
  { transform:'translate(0,0) scale(1,1)', opacity:1 }
], { duration:480, easing:'cubic-bezier(.22,.85,.28,1)' });
```

`sx/sy` are deliberately non-uniform (card aspect != modal aspect); it reads as
a zoom, not a stretch. On close, skip the FLIP when the target card is scrolled
out of view and fade instead. Cancel in-flight animations before restarting, but
only anonymous ones (`if (!a.animationName) a.cancel()`) or you will kill the
CSS keyframe fades.

## Auto-play

`?autoplay=1` opens cards in order with a `?dwell=` (default 3000 ms) hold,
shows a banner with a live counter, and hands control back on the first
`pointerdown`/`keydown` (captured, so a click on a card also stops it).
`?loop=1` keeps going past the last card. The loop is
`openModal(i, cards[i])` -> wait dwell -> `closeModal()` -> wait 340 ms -> next.

## Accessibility

`role="dialog"` + `aria-modal="true"` + `aria-labelledby` on the modal; focus
the dialog on open with `{ preventScroll: true }`; trap `Tab`; `Escape` closes,
`ArrowLeft/Right` navigate, `Space` re-speaks; `aria-live="polite"` toast for
"speech unsupported"; honour `prefers-reduced-motion` by skipping FLIP and
shortening reveal delays.

## Gotchas learned the hard way

- A generic class name (`.zh`) used in both the modal and the footer silently
  cross-contaminates layouts. Prefix component classes (`.meaning`,
  `.colophon-zh`).
- `mix-blend-mode: multiply` on a white-background illustration leaves a visible
  rectangle over tinted cards. Use a real alpha channel instead (see
  art-pipeline.md).
- Full-page headless screenshots can render below-fold images blank — a Chrome
  capture artifact. Verify with scrolled viewport shots plus
  `img.complete && img.naturalWidth > 0`.
- Pick a non-obvious dev-server port; `4173`/`8000` collide with other projects
  and you end up screenshotting a different app.
