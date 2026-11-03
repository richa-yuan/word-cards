#!/usr/bin/env python3
"""Build the voice track for the card video with neural TTS (edge-tts).

Same timeline as the skill's build_audio.py (intro / dwell / outro, tap click,
word at +0.42, gloss after), but the speech is rendered by Edge neural voices
instead of macOS `say`, which is far more natural for a kids' clip.

  python3 build_audio_neural.py --data assets/data.js --out /tmp/track.wav \
      [--en-voice en-US-JennyNeural] [--zh-voice zh-CN-XiaoxiaoNeural] \
      [--intro 4.4] [--dwell 3.0] [--outro 6.2] [--intro-text '...'] [--outro-text '...']
"""
import argparse, asyncio, math, os, re, struct, subprocess, sys, json

import edge_tts

SR = 22050


def load_words(path):
    txt = open(path, encoding='utf-8').read()
    out = []
    for line in txt.splitlines():
        m = re.search(r"name\s*:\s*'([^']*)'.*?zh\s*:\s*'([^']*)'", line)
        if m:
            out.append((m.group(1), m.group(2)))
    if not out:
        sys.exit('error: no {name, zh} entries found in ' + path)
    return out


async def render(text, voice, rate, path, sem):
    async with sem:
        for attempt in range(3):
            try:
                c = edge_tts.Communicate(text, voice, rate=rate)
                await c.save(path)
                if os.path.getsize(path) > 1000:
                    return
            except Exception as e:
                if attempt == 2:
                    raise
                await asyncio.sleep(1.2 * (attempt + 1))


def to_pcm(path):
    raw = subprocess.run(
        ['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'],
        check=True, stdout=subprocess.PIPE).stdout
    return list(struct.unpack('<%df' % (len(raw) // 4), raw))


def trim(samples, thresh=0.006, pad=0.03):
    """Cut leading/trailing silence so every clip starts right on the beat."""
    n = len(samples)
    a, b = 0, n
    while a < n and abs(samples[a]) < thresh:
        a += 1
    while b > a and abs(samples[b - 1]) < thresh:
        b -= 1
    p = int(pad * SR)
    return samples[max(0, a - p):min(n, b + p)]


async def main_async(a, words):
    tmp = '/tmp/_neural_tts'
    os.makedirs(tmp, exist_ok=True)
    jobs = []
    for i, (en, zh) in enumerate(words):
        jobs.append((f'en{i}', en, a.en_voice, a.en_rate))
        if zh and not a.no_zh:
            jobs.append((f'zh{i}', zh, a.zh_voice, a.zh_rate))
    if a.outro_text:
        jobs.append(('outro', a.outro_text, a.zh_voice, '-8%'))
    if a.intro_text:
        jobs.append(('intro', a.intro_text, a.zh_voice, a.zh_rate))

    sem = asyncio.Semaphore(6)
    await asyncio.gather(*[render(t, v, r, f'{tmp}/{k}.mp3', sem) for k, t, v, r in jobs])

    clips = {k: trim(to_pcm(f'{tmp}/{k}.mp3')) for k, _, _, _ in jobs}

    n = len(words)
    cards_end = a.intro + n * a.dwell
    total = cards_end + a.outro
    buf = [0.0] * int(total * SR)

    def put(s, t, gain=1.0):
        i0 = int(t * SR)
        for k, v in enumerate(s):
            j = i0 + k
            if 0 <= j < len(buf):
                buf[j] += v * gain

    def tone(t, freq, dur, amp, decay=18.0):
        i0, cnt = int(t * SR), int(dur * SR)
        for k in range(cnt):
            j = i0 + k
            if 0 <= j < len(buf):
                buf[j] += amp * math.exp(-decay * k / SR) * math.sin(2 * math.pi * freq * k / SR)

    tone(a.intro - 0.72, 1400, 0.06, a.click)
    intro_end = None
    if a.intro_text:
        iv = clips['intro']
        put(iv, a.intro_at, 0.9)
        intro_end = a.intro_at + len(iv) / SR
    rows, over = [], []
    for i, (en, zh) in enumerate(words):
        base = a.intro + i * a.dwell
        tone(base + 0.06, 1400, 0.06, a.click * 0.85)
        e = clips[f'en{i}']
        put(e, base + 0.42, 0.95)
        end = base + 0.42 + len(e) / SR
        if zh and not a.no_zh:
            z = clips[f'zh{i}']
            tz = max(base + 1.55, end + 0.26)
            put(z, tz, 0.82)
            end = tz + len(z) / SR
        used = end - base
        rows.append((i + 1, en, round(len(e) / SR, 2), round(used, 2)))
        if used > a.dwell - 0.2:
            over.append((i + 1, en, round(used, 2)))

    outro_end = None
    if a.outro_text:
        tone(cards_end + 0.1, 880, 0.5, 0.06, decay=7)
        tone(cards_end + 0.1, 1320, 0.5, 0.045, decay=7)
        ov = clips['outro']
        put(ov, cards_end + 0.6, 0.86)
        outro_end = cards_end + 0.6 + len(ov) / SR

    peak = max(abs(v) for v in buf) or 1.0
    g = 0.9 / peak
    import wave
    w = wave.open(a.out, 'wb')
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(b''.join(struct.pack('<h', int(max(-1, min(1, v * g)) * 32767)) for v in buf))
    w.close()

    print('wrote %s  %.1fs  peak %.2f -> gain %.2f' % (a.out, total, peak, g))
    print('card  word                  en_s  slot_used')
    for r in rows:
        print('%4d  %-21s %4.2f  %5.2f' % r)
    print('timeline: intro %.1fs + %d cards x %.1fs + outro %.1fs = %.1fs'
          % (a.intro, n, a.dwell, a.outro, total))
    if intro_end is not None:
        air = a.intro - 0.72 - intro_end
        print('intro line ends at %.2fs -> %.2fs of air before the deck tap' % (intro_end, air))
        if air < 0.25:
            print('WARNING: the intro line runs into the deck tap; shorten it or raise --intro')
    if over:
        print('WARNING: slots nearly fill the dwell:')
        for i, en, used in over:
            print('  card %d %s = %.2fs of %.1fs' % (i, en, used, a.dwell))
    else:
        print('all cards fit inside the %.1fs dwell' % a.dwell)
    if outro_end is not None:
        print('outro ends at %.2fs -> %.2fs tail' % (outro_end, total - outro_end))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', default='track.wav')
    ap.add_argument('--intro', type=float, default=4.4)
    ap.add_argument('--dwell', type=float, default=3.0)
    ap.add_argument('--outro', type=float, default=7.4)
    ap.add_argument('--intro-text', default='')
    ap.add_argument('--intro-at', type=float, default=0.40,
                    help='when the intro line starts inside the intro')
    ap.add_argument('--en-voice', default='en-US-JennyNeural')
    ap.add_argument('--zh-voice', default='zh-CN-XiaoxiaoNeural')
    ap.add_argument('--en-rate', default='-8%')
    ap.add_argument('--zh-rate', default='-4%')
    ap.add_argument('--no-zh', action='store_true')
    ap.add_argument('--outro-text', default='')
    ap.add_argument('--click', type=float, default=0.075)
    a = ap.parse_args()
    asyncio.run(main_async(a, load_words(a.data)))
