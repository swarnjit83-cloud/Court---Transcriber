#!/usr/bin/env python3
"""Neural TTS (Kokoro) voice-over timed to the four word-hits, mixed into the score and muxed onto the video.
usage: make_voiceover.py <kokoro.onnx> <voices.bin> <score.wav> <video_in.mp4> <video_out.mp4>"""
import sys, subprocess, wave, numpy as np
from kokoro_onnx import Kokoro
SR = 44100
model, voices, score, vin, vout = sys.argv[1:6]
k = Kokoro(model, voices)
LINES = [("No race.", 11.0, 1.10), ("No chase.", 11.625, 1.12), ("I'm winning", 12.25, 1.18), ("at my pace.", 12.875, 0.88)]
VOICE = "am_onyx"

def resample(x, sr):
    n = int(len(x) * SR / sr); return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
def trim(x, th=0.01):
    idx = np.where(np.abs(x) > th)[0]; return x[idx[0]:idx[-1] + 1] if len(idx) else x

vo = np.zeros(int(15 * SR)); 
for txt, t0, spd in LINES:
    y, sr = k.create(txt, voice=VOICE, speed=spd, lang="en-us")
    y = trim(resample(np.asarray(y, np.float64), sr))
    y = y / np.abs(y).max()
    nxt = [l[1] for l in LINES if l[1] > t0]; mx = int(((nxt[0] - t0) - 0.03) * SR) if nxt else len(y)
    if len(y) > mx: y = y[:mx]; f = int(0.06 * SR); y[-f:] *= np.linspace(1, 0, f)
    onset = int(0.012 * SR)                      # consonant lands right on the beat
    i = int(t0 * SR) - onset; vo[i:i + len(y)] += y[:len(vo) - i]
    print(txt, round(len(y) / SR, 2), 's')
# voice polish: warmth, saturation, short slap echo + small room
low = np.convolve(vo, np.ones(60) / 60, 'same'); vo = vo + 0.45 * low
vo = np.tanh(2.2 * vo) / np.tanh(2.2) * 0.95
echo = np.zeros_like(vo); d = int(0.18 * SR); echo[d:] = vo[:-d] * 0.28
rng = np.random.default_rng(1); ir = rng.normal(size=int(0.7 * SR)) * np.exp(-np.arange(int(0.7 * SR)) / SR * 6); ir /= np.abs(ir).sum() / 2.2
n = len(vo) + len(ir); nf = 1 << (n - 1).bit_length()
room = np.fft.irfft(np.fft.rfft(vo, nf) * np.fft.rfft(ir, nf), nf)[:len(vo)]
vo_s = vo + echo + 0.22 * room
# mix: duck music while the voice speaks
with wave.open(score) as w: a = np.frombuffer(w.readframes(w.getnframes()), '<i2').reshape(-1, 2) / 32768.0
env = np.convolve(np.abs(vo), np.ones(int(0.12 * SR)) / int(0.12 * SR), 'same'); env = np.clip(env * 6, 0, 1)
duck = 1 - 0.38 * env
mix = a * duck[:len(a), None] + vo_s[:len(a), None] * 0.95 * np.array([[1, 1]])
mix = np.tanh(1.1 * mix) / np.tanh(1.1) * 0.84
with wave.open('mix_vo.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(mix, -1, 1) * 32767).astype('<i2').tobytes())
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', vin, '-i', 'mix_vo.wav', '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '224k', '-t', '15', '-movflags', '+faststart', vout], check=True)
print('ok', vout)
