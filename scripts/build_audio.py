#!/usr/bin/env python3
"""Build the voice/click track for a card video from the app's word list.

  python3 build_audio.py --data assets/data.js --out track.wav \
      [--intro 3.4] [--dwell 3.0] [--en-voice Samantha] [--zh-voice Tingting]

`--data` accepts either a JSON array of {name, zh} or the app's data.js
(lines shaped like `{ name:'celery', ... zh:'芹菜', ... }`).

Timing per card slot: tap click at +0.06, word at +0.42, gloss after the word.
Prints a per-card table and warns on any slot that overruns the dwell.
"""
import argparse, json, math, os, re, struct, subprocess, sys, wave

SR = 22050


def load_words(path):
    txt = open(path, encoding='utf-8').read()
    try:
        data = json.loads(txt)
        return [(d.get('name'), d.get('zh', '')) for d in data]
    except Exception:
        pass
    out = []
    for line in txt.splitlines():
        m = re.search(r"name\s*:\s*'([^']*)'.*?zh\s*:\s*'([^']*)'", line)
        if m:
            out.append((m.group(1), m.group(2)))
    if not out:
        sys.exit('error: no {name, zh} entries found in ' + path)
    return out


def say(text, voice, rate):
    """Return PCM samples (floats) for one utterance via macOS `say`."""
    tmp = '/tmp/_card_tts_%d.wav' % os.getpid()
    subprocess.run(['say', '-v', voice, '-r', str(rate),
                    '--data-format=LEI16@%d' % SR, '-o', tmp, text], check=True)
    w = wave.open(tmp, 'rb')
    raw = w.readframes(w.getnframes())
    w.close()
    os.remove(tmp)
    return [s / 32768 for s in struct.unpack('<%dh' % (len(raw) // 2), raw)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', default='track.wav')
    ap.add_argument('--intro', type=float, default=3.4)
    ap.add_argument('--dwell', type=float, default=3.0)
    ap.add_argument('--outro', type=float, default=4.2)
    ap.add_argument('--en-voice', default='Samantha')
    ap.add_argument('--zh-voice', default='Tingting')
    ap.add_argument('--en-rate', type=int, default=172)
    ap.add_argument('--zh-rate', type=int, default=170)
    ap.add_argument('--no-zh', action='store_true')
    ap.add_argument('--outro-text', default='')
    ap.add_argument('--click', type=float, default=0.085, help='tap click level, 0 to mute')
    a = ap.parse_args()

    words = load_words(a.data)
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
    rows, over = [], []
    for i, (en, zh) in enumerate(words):
        base = a.intro + i * a.dwell
        tone(base + 0.06, 1400, 0.06, a.click * 0.85)
        e = say(en, a.en_voice, a.en_rate)
        put(e, base + 0.42, 0.95)
        end = base + 0.42 + len(e) / SR
        if not a.no_zh and zh:
            z = say(zh, a.zh_voice, a.zh_rate)
            tz = max(base + 1.55, end + 0.28)
            put(z, tz, 0.80)
            end = tz + len(z) / SR
        used = end - base
        rows.append((i + 1, en, round(len(e) / SR, 2), round(used, 2)))
        if used > a.dwell - 0.25:
            over.append((i + 1, en, round(used, 2)))

    outro_end = None
    if a.outro_text:
        tone(cards_end + 0.1, 880, 0.5, 0.07, decay=7)
        tone(cards_end + 0.1, 1320, 0.5, 0.05, decay=7)
        ov = say(a.outro_text, a.zh_voice, 168)
        put(ov, cards_end + 0.55, 0.85)
        outro_end = cards_end + 0.55 + len(ov) / SR

    peak = max(abs(v) for v in buf) or 1.0
    g = 0.88 / peak
    w = wave.open(a.out, 'wb')
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(b''.join(struct.pack('<h', int(max(-1, min(1, v * g)) * 32767)) for v in buf))
    w.close()

    print('wrote %s  %.1fs  peak %.2f -> gain %.2f' % (a.out, total, peak, g))
    print('card  word            en_s  slot_used')
    for r in rows:
        print('%4d  %-15s %4.2f  %5.2f' % r)
    print('timeline: intro %.1fs + %d cards x %.1fs + outro %.1fs = %.1fs'
          % (a.intro, n, a.dwell, a.outro, total))
    if over:
        print('WARNING: these slots nearly fill the dwell (raise --dwell or drop --no-zh):')
        for i, en, used in over:
            print('  card %d %s = %.2fs of %.1fs' % (i, en, used, a.dwell))
    else:
        print('all cards fit inside the %.1fs dwell' % a.dwell)
    if outro_end is not None:
        tail = total - outro_end
        print('outro line ends at %.2fs -> %.2fs of visual tail' % (outro_end, tail))
        if tail < 0.6:
            print('WARNING: the outro line runs to the end of the clip; shorten it, '
                  'raise --outro, or drop --outro-text')


if __name__ == '__main__':
    main()
