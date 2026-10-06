#!/bin/sh
# usage: loop15.sh <generated video, 24 fps> <output.mp4> [scale WxH]
# Real tempo of the source dance = 83.35 BPM (beat 0.7199 s); the clip starts on a beat. Restart the dance after
# 3 bars (12 beats = 8.638 s) so steps stay on the beat and on the bar; music = Suno track 2 from 1.834 s, whose
# accents best match the original audio (onset correlation 0.34).
IN="$1"; OUT="$2"; SC="${3:-}"
VF="[0:v]trim=0:8.638,setpts=PTS-STARTPTS[a];[0:v]trim=0:6.362,setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1:a=0[v]"
if [ -n "$SC" ]; then VF="$VF;[v]scale=$SC:flags=lanczos[v2]"; MAP="[v2]"; else MAP="[v]"; fi
ffmpeg -y -loglevel error -i "$IN" -i toctoc83_audio_15s.m4a -filter_complex "$VF" -map "$MAP" -map 1:a -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -c:a copy -movflags +faststart -t 15 "$OUT"
