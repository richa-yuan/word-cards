#!/bin/bash
# Encode captured frames + audio into a Douyin-ready vertical MP4.
#
#   encode.sh FRAMES_DIR AUDIO_WAV OUT_MP4 [FPS] [SIZE] [FFMPEG]
#
# Defaults: 30 fps, 1080x1920, H.264 High / yuv420p limited range / BT.709,
# AAC 192k 44.1kHz stereo, +faststart. All of those are what Douyin re-muxes
# without surprises; JPEG frames are full-range, so the range is converted
# explicitly instead of leaving a yuvj420p tag behind.
set -euo pipefail

FRAMES=${1:?usage: encode.sh FRAMES_DIR AUDIO_WAV OUT_MP4 [FPS] [SIZE] [FFMPEG]}
AUDIO=${2:?missing audio wav}
OUT=${3:?missing output mp4}
FPS=${4:-30}
SIZE=${5:-1080x1920}
FF=${6:-ffmpeg}
W=${SIZE%x*}; H=${SIZE#*x}

command -v "$FF" >/dev/null 2>&1 || [ -x "$FF" ] || { echo "error: ffmpeg not found at $FF"; exit 1; }
[ -d "$FRAMES" ] || { echo "error: no frame dir $FRAMES"; exit 1; }

"$FF" -y -framerate "$FPS" -i "$FRAMES/f-%05d.jpg" -i "$AUDIO" \
  -vf "scale=$W:$H:in_range=full:out_range=limited:flags=lanczos,format=yuv420p" \
  -c:v libx264 -preset slow -crf 17 -profile:v high -level 4.0 \
  -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
  -c:a aac -b:a 192k -ar 44100 -ac 2 -shortest -movflags +faststart \
  "$OUT" 2> >(grep -E 'Error|error' >&2 || true)

"$FF" -hide_banner -i "$OUT" 2>&1 \
  | grep -E 'Duration|Stream' \
  | sed -E 's/^ +//' || true
echo "ok: $OUT ($(du -h "$OUT" | cut -f1))"
