#!/usr/bin/env python3
"""Generate illustration grids with a LOCAL Draw Things HTTP API.

Draw Things (macOS app, Apple Silicon) ships an AUTOMATIC1111-compatible HTTP
API on 127.0.0.1:7860. This script talks to it directly, so no cloud call and
no API key is needed. Output is a 2x2 grid PNG per job, ready for slice_grid.py.

  # 1) health check (a REAL tiny generation — Draw Things has no /sd-models)
  python3 draw_things_gen.py --check

  # 2) one grid from a prompt
  python3 draw_things_gen.py --prompt "A 2x2 grid of ..." --out /tmp/grid1.png

  # 3) batch from a manifest (recommended for a full deck)
  python3 draw_things_gen.py --manifest grids.json --out /tmp/dtgrids

manifest format:
{
  "defaults": {"steps": 20, "cfg_scale": 7.0, "size": "1024x1024",
               "negative_prompt": "text, label, logo, watermark, hands"},
  "grids": [
    {"out": "grid1.png", "prompt": "A 2x2 grid of four ..."},
    {"out": "grid2.png", "quadrants": ["top-left ...", "top-right ...",
                                       "bottom-left ...", "bottom-right ..."]}
  ]
}

`prompt` renders one image holding all four quadrants (matches art-pipeline.md).
`quadrants` renders 4 separate images and composes them into a 2x2 grid — more
reliable if the loaded model is weak at quadrant layout. Both produce the same
grid PNG that slice_grid.py expects.

Draw Things gotchas baked in here:
  - server must be ON in app Settings > Advanced > API Server, Protocol = HTTP,
    TLS off, IP 127.0.0.1; the app must stay open while generating.
  - GET /sdapi/v1/sd-models returns 404 -> health check is a real txt2img call.
  - model is the one currently loaded in the app; NOT settable per request.
  - width/height must be multiples of 64.
  - first call after launch can take 30-60s (model warm-up) -> long timeout + retry.
  - response is JSON {"images": ["<base64 PNG>", ...]}; base64 starts iVBORw.
  - FLUX.1-schnell: steps=4, cfg_scale=1.0. SD1.5/SDXL: steps~25, cfg~7.
"""
import argparse
import base64
import json
import os
import struct
import sys
import time
import urllib.error
import urllib.request

PNG_MAGIC_B64 = 'iVBORw'  # base64 prefix of a real PNG


def api_url(host, port, path='/sdapi/v1/txt2img'):
    return 'http://%s:%d%s' % (host, port, path)


def call_txt2img(payload, args, timeout=None):
    """POST one txt2img request. Returns the list of base64 PNG strings."""
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        api_url(args.host, args.port),
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    tmo = timeout or args.timeout
    with urllib.request.urlopen(req, timeout=tmo) as resp:
        raw = resp.read()
    data = json.loads(raw.decode('utf-8'))
    imgs = data.get('images') or []
    if not imgs:
        raise RuntimeError('API returned no images: ' + raw[:200].decode('utf-8', 'replace'))
    return imgs


def healthy(args):
    """Real generation as a health probe. Returns the model's warm-up note."""
    probe = {
        'prompt': 'a small red apple',
        'steps': 1,
        'width': 64,
        'height': 64,
        'cfg_scale': 1.0,
        'batch_size': 1,
    }
    t0 = time.time()
    imgs = call_txt2img(probe, args, timeout=args.timeout)
    if not imgs[0].startswith(PNG_MAGIC_B64):
        return False, 'probe response is not a PNG (got %r)' % imgs[0][:40]
    return True, 'Draw Things replied in %.1fs; model is loaded and warm.' % (time.time() - t0)


def save_b64(b64str, path):
    raw = base64.b64decode(b64str)
    if not raw.startswith(b'\x89PNG'):
        raise RuntimeError('decoded bytes are not a PNG: ' + path)
    with open(path, 'wb') as f:
        f.write(raw)
    return len(raw)


def grid_payload(prompt, size, steps, cfg, negative, seed, batch=1):
    w, h = (int(x) for x in size.lower().split('x'))
    if w % 64 or h % 64:
        raise ValueError('width/height must be multiples of 64 (got %dx%d)' % (w, h))
    p = {
        'prompt': prompt,
        'steps': steps,
        'width': w,
        'height': h,
        'cfg_scale': cfg,
        'batch_size': batch,
    }
    if negative:
        p['negative_prompt'] = negative
    if seed is not None and seed >= 0:
        p['seed'] = seed
    return p


def compose_grid(paths, out_path, size):
    """Compose 4 quadrant PNGs into one 2x2 grid PNG (PIL already a skill dep)."""
    from PIL import Image
    w, h = (int(x) for x in size.lower().split('x'))
    grid = Image.new('RGB', (w, h), 'white')
    for i, p in enumerate(paths):
        im = Image.open(p).convert('RGB').resize((w // 2, h // 2), Image.LANCZOS)
        grid.paste(im, ((i % 2) * (w // 2), (i // 2) * (h // 2)))
    grid.save(out_path, 'PNG')
    return out_path


def generate_one(job, defaults, args, out_dir):
    name = job.get('out') or ('dt-grid-%d.png' % int(time.time() * 1000))
    out_path = name if os.path.isabs(name) else os.path.join(out_dir, name)
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)

    size = job.get('size', defaults['size'])
    steps = job.get('steps', defaults['steps'])
    cfg = job.get('cfg_scale', defaults['cfg_scale'])
    negative = job.get('negative_prompt', defaults['negative_prompt'])
    seed = job.get('seed', defaults['seed'])

    if 'prompt' in job and 'quadrants' not in job:
        payload = grid_payload(job['prompt'], size, steps, cfg, negative, seed)
        imgs = call_txt2img_with_retry(payload, args)
        nbytes = save_b64(imgs[0], out_path)
        print('ok  %-28s  %6d bytes  (single grid prompt)' % (os.path.basename(out_path), nbytes))
        return out_path

    if 'quadrants' in job:
        qs = job['quadrants']
        if len(qs) != 4:
            raise ValueError('quadrants must have exactly 4 prompts, got %d' % len(qs))
        qw, qh = (int(x) for x in size.lower().split('x'))
        qsize = '%dx%d' % (qw // 2, qh // 2)
        tmp_paths = []
        for i, q in enumerate(qs):
            payload = grid_payload(q, qsize, steps, cfg, negative,
                                   None if seed is None else seed + i)
            imgs = call_txt2img_with_retry(payload, args)
            tp = os.path.join(os.path.dirname(out_path),
                              '_dtquad_%s_%d.png' % (os.path.basename(out_path), i))
            save_b64(imgs[0], tp)
            tmp_paths.append(tp)
        compose_grid(tmp_paths, out_path, size)
        for tp in tmp_paths:
            os.remove(tp)
        print('ok  %-28s  composed from 4 quadrants' % os.path.basename(out_path))
        return out_path

    raise ValueError('job needs either "prompt" or "quadrants": %r' % job)


def call_txt2img_with_retry(payload, args):
    last = None
    for attempt in range(args.retries):
        try:
            return call_txt2img(payload, args)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError,
                RuntimeError, ValueError, json.JSONDecodeError) as e:
            last = e
            if attempt == args.retries - 1:
                break
            wait = args.retry_wait * (attempt + 1)
            print('  retry %d/%d after %.1fs: %s' % (attempt + 1, args.retries - 1, wait, e),
                  file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError('Draw Things request failed after %d tries: %s' % (args.retries, last))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=7860)
    ap.add_argument('--timeout', type=float, default=180.0, help='per-request timeout (s); first call warms up')
    ap.add_argument('--retries', type=int, default=3)
    ap.add_argument('--retry-wait', type=float, default=3.0)
    ap.add_argument('--check', action='store_true', help='health check via a real tiny generation')
    ap.add_argument('--prompt', help='single 2x2 grid prompt (with --out)')
    ap.add_argument('--out', help='output PNG path (with --prompt)')
    ap.add_argument('--manifest', help='JSON manifest with defaults + grids')
    ap.add_argument('--size', default='1024x1024')
    ap.add_argument('--steps', type=float, default=20)
    ap.add_argument('--cfg', type=float, default=7.0, dest='cfg_scale')
    ap.add_argument('--negative', default='text, label, logo, watermark, signature, hands')
    ap.add_argument('--seed', type=int, default=-1)
    args = ap.parse_args()

    if args.check:
        try:
            ok, msg = healthy(args)
        except Exception as e:
            print('FAIL  Draw Things not reachable at %s' % api_url(args.host, args.port))
            print('      %s' % e)
            print('      Open Draw Things > Settings > Advanced > API Server:')
            print('      Server Online = ON, Protocol = HTTP, TLS = OFF, IP = 127.0.0.1.')
            sys.exit(1)
        print(('PASS  ' if ok else 'FAIL  ') + msg)
        sys.exit(0 if ok else 1)

    if args.prompt:
        if not args.out:
            ap.error('--prompt requires --out')
        defaults = {'size': args.size, 'steps': args.steps, 'cfg_scale': args.cfg_scale,
                    'negative_prompt': args.negative, 'seed': args.seed}
        out_dir = os.path.dirname(os.path.abspath(args.out))
        generate_one({'prompt': args.prompt, 'out': args.out}, defaults, args, out_dir)
        return

    if args.manifest:
        m = json.load(open(args.manifest, encoding='utf-8'))
        defaults = {
            'size': m.get('defaults', {}).get('size', args.size),
            'steps': m.get('defaults', {}).get('steps', args.steps),
            'cfg_scale': m.get('defaults', {}).get('cfg_scale', args.cfg_scale),
            'negative_prompt': m.get('defaults', {}).get('negative_prompt', args.negative),
            'seed': m.get('defaults', {}).get('seed', args.seed),
        }
        # In manifest mode --out is an output DIRECTORY (overrides the default
        # of "next to the manifest"). Relative job.out names land inside it.
        out_dir = os.path.abspath(args.out) if args.out else os.path.dirname(os.path.abspath(args.manifest))
        os.makedirs(out_dir, exist_ok=True)
        made = []
        for job in m['grids']:
            try:
                made.append(generate_one(job, defaults, args, out_dir))
            except Exception as e:
                print('FAIL  job %r: %s' % (job.get('out'), e), file=sys.stderr)
                sys.exit(1)
        print('\n%d grids -> %s' % (len(made), out_dir))
        print('next: python3 slice_grid.py --manifest <grids-for-slicing.json> --out assets/img')
        return

    ap.error('pass --check, --prompt + --out, or --manifest')


if __name__ == '__main__':
    main()
