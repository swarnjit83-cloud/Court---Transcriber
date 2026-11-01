#!/usr/bin/env python3
"""Synthesize the 15 s score: 96 BPM hip-hop, bass drop at 11.0 s. Writes a stereo 44.1 kHz WAV."""
import math, sys, wave
import numpy as np

SR = 44100; DUR = 15.0; N = int(SR * DUR)
BEAT = 0.625; STEP = BEAT / 4; ORIGIN = 1.0      # bar lines at 1.0, 3.5, 6.0, 8.5, 11.0, 13.5
L = np.zeros(N); R = np.zeros(N); VL = np.zeros(N); VR = np.zeros(N)
rng = np.random.default_rng(7)

def T(d): return np.arange(int(d * SR)) / SR
def hp(x, k=1): 
    for _ in range(k): x = np.diff(x, prepend=0.0)
    return x
def place(sig, t0, g=1.0, pan=0.0, verb=0.0):
    i = int(round(t0 * SR))
    if i >= N or i + len(sig) <= 0: return
    s = sig
    if i < 0: s = s[-i:]; i = 0
    n = min(len(s), N - i); s = s[:n]
    gl = g * math.cos((pan + 1) * math.pi / 4); gr = g * math.sin((pan + 1) * math.pi / 4)
    L[i:i+n] += s * gl; R[i:i+n] += s * gr
    if verb: VL[i:i+n] += s * verb; VR[i:i+n] += s * verb

def kick(hard=True):
    t = T(0.5); f = 44 + 130 * np.exp(-t * 38)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)
    if hard: y += 0.45 * np.sin(2 * np.pi * 2200 * t) * np.exp(-t * 400)
    return np.tanh(1.8 * y)
def softkick():
    t = T(0.6); f = 40 + 55 * np.exp(-t * 22)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 5)
def snare():
    t = T(0.35); n = hp(rng.normal(size=len(t)))
    return (n * np.exp(-t * 17) * 0.55 + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 28) * 0.5)
def clap():
    t = T(0.4); n = hp(rng.normal(size=len(t)))
    env = sum(np.where(t >= k, np.exp(-np.maximum(t - k, 0) * 230), 0) for k in (0, .011, .022))
    env = env + 0.55 * np.where(t >= .03, np.exp(-(t - .03) * 13), 0)
    return np.convolve(n * env, [.25, .5, .25], 'same') * 1.3
def hat(open_=False, d=0.12):
    t = T(d if not open_ else 0.4); n = hp(rng.normal(size=len(t)), 2)
    return n * np.exp(-t * (13 if open_ else 75)) * 0.5
def bass(freq, dur):
    t = T(dur + 0.3); f = freq * (1 + 0.7 * np.exp(-t * 45)); ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) + 0.28 * np.sin(2 * ph) + 0.10 * np.sin(3 * ph)
    env = (1 - np.exp(-t * 700)) * np.exp(-t * 1.5) * np.clip((dur + 0.08 - t) / 0.08, 0, 1)
    return np.tanh(2.2 * y * env) * 0.85
def pluck(freq, d=0.7):
    t = T(d); y = 0
    for h, a in ((1, 1), (2, .5), (3, .32), (4, .18), (5, .1)):
        y = y + a * np.sin(2 * np.pi * freq * h * t) * np.exp(-t * (4 + 3 * h))
    return y * np.minimum(t / 0.004, 1) * 0.45
def stab(freqs, d=0.55):
    t = T(d); y = 0
    for f in freqs:
        for det in (1.0, 1.006):
            ph = 2 * np.pi * f * det * t
            y = y + (np.sin(ph) + .5 * np.sin(2 * ph) + .33 * np.sin(3 * ph) + .25 * np.sin(4 * ph))
    return y * np.exp(-t * 5.5) * np.minimum(t / 0.003, 1) * 0.11
def riser(d):
    t = T(d); x = t / d; f = 180 * np.exp(x * math.log(24)); ph = 2 * np.pi * np.cumsum(f) / SR
    y = (np.sin(ph) + .5 * np.sin(2 * ph) + .3 * np.sign(np.sin(ph * 1.012))) * x ** 2.3 * 0.30
    return y + hp(rng.normal(size=len(t)), 1) * x ** 3 * 0.35
def revcym(d):
    t = T(d); return hp(rng.normal(size=len(t)), 2) * (t / d) ** 3 * 0.5
def whoosh(d=0.35):
    t = T(d); n = np.convolve(rng.normal(size=len(t)), np.ones(3) / 3, 'same')
    return hp(n) * np.sin(np.pi * t / d) ** 2 * 0.7
def boom(d=3.0):
    t = T(d); f = 32 + 95 * np.exp(-t * 11); ph = 2 * np.pi * np.cumsum(f) / SR
    n = np.convolve(rng.normal(size=len(t)), np.ones(10) / 10, 'same') * np.exp(-t * 5) * 0.5
    return np.tanh(1.7 * (np.sin(ph) * np.exp(-t * 0.95) * 1.2 + n))
def tick(f): t = T(0.04); return np.sin(2 * np.pi * f * t) * np.exp(-t * 500) * 0.8
def ping():
    t = T(0.45); return (np.sin(2 * np.pi * 1760 * t) * np.exp(-t * 14) * .35 + np.sin(2 * np.pi * 2637 * t) * np.exp(-t * 20) * .18)
def pad(freqs, d):
    t = T(d); y = 0
    for f in freqs:
        for det in (0.997, 1.003):
            y = y + np.sin(2 * np.pi * f * det * t + rng.uniform(0, 6))
    return y * np.sin(np.pi * np.minimum(t / d, 1) ** 0.8) ** 1.5 * 0.05

F1, Ab1, Bb1, C2 = 43.65, 51.91, 58.27, 65.41
F4, Ab4, C5, Eb5 = 349.2, 415.3, 523.3, 622.3
Fm = [174.6, 207.7, 261.6]

def sx(bar0, s): return bar0 + s * STEP
def groove(b0, bar_idx, hats=True, bassline=True, arp=True, fills=False):
    for s in (0, 6, 10) + ((13,) if bar_idx % 2 else ()): place(kick(), sx(b0, s), 0.95)
    for s in (4, 12):
        place(snare(), sx(b0, s), 0.5, verb=0.2); place(clap(), sx(b0, s), 0.55, verb=0.35)
    if hats:
        for s in range(0, 16, 2):
            place(hat(), sx(b0, s), (0.55 if s % 4 == 0 else 0.32), pan=0.35 if (s // 2) % 2 else -0.35)
        for s in ((14, 15) if bar_idx % 2 else ()): place(hat(), sx(b0, s), 0.3, pan=0.3)
        place(hat(True), sx(b0, 14 if bar_idx % 2 == 0 else 7), 0.35, pan=0.2)
    if bassline:
        notes = ([(0, F1, 5), (6, F1, 3), (10, Ab1, 3), (13, C2, 2)] if bar_idx % 2 == 0
                 else [(0, F1, 5), (6, Bb1, 3), (10, Ab1, 3), (13, F1, 2)])
        for s, f, ln in notes: place(bass(f, ln * STEP), sx(b0, s), 0.95)
    if arp:
        seq = [(0, F4), (3, Ab4), (6, C5), (8, Ab4), (11, Eb5), (14, C5)]
        for k, (s, f) in enumerate(seq):
            place(pluck(f), sx(b0, s), 0.5, pan=-0.4 if k % 2 else 0.4, verb=0.3)
            place(pluck(f), sx(b0, s) + 3 * STEP, 0.2, pan=0.5 if k % 2 else -0.5, verb=0.3)   # echo

# ------------------------------------------------------------ A: 0-3 s  (everyone is running)
for k in range(0, 48):
    t0 = k * STEP * 1.0
    if t0 >= 3.0: break
    place(hat(), t0, 0.12 + 0.5 * (t0 / 3.0), pan=0.4 if k % 2 else -0.4)
for t0 in (1.0, 1.625, 2.25, 2.5, 2.625, 2.75, 2.875): place(kick(), t0, 0.9)
for k, t0 in enumerate(np.arange(0, 3.0, 0.5)): place(tick(2300 if k % 2 == 0 else 1300), t0, 0.5)
for t0 in (0.35, 1.1, 1.8, 2.3): place(ping(), t0, 0.5, pan=0.5, verb=0.3)
for t0 in (0.0, 0.45, 0.9, 1.4, 1.95, 2.5): place(whoosh(), t0, 0.6, pan=rng.uniform(-.6, .6))
for k, t0 in enumerate(np.concatenate([np.arange(2.375, 2.625, 0.125), np.arange(2.625, 2.85, 0.0625), np.arange(2.85, 3.0, 0.03)])):
    place(snare(), t0, 0.25 + 0.35 * k / 12, verb=0.1)
place(revcym(1.0), 2.0, 0.8)
tt = T(3.0); place(np.sin(2 * np.pi * 55 * tt) * (0.25 + 0.5 * tt / 3) * (0.6 + 0.4 * np.sin(2 * np.pi * (3 + 4 * tt) * tt)) * 0.35, 0, 1.0)

# ------------------------------------------------------------ B: 3-6 s  (slow motion)
place(boom(), 3.0, 1.0, verb=0.2)
place(pad(Fm + [349.2], 3.0), 3.0, 1.0, verb=0.5)
for t0 in (3.5, 4.125, 4.75, 5.375): place(softkick(), t0, 0.9)
for t0, f in ((3.5, F1), (4.75, Ab1)): place(bass(f, 1.0), t0, 0.7)
for k in range(10): place(hat(True), 3.25 + k * 0.3125, 0.12, pan=-0.3 if k % 2 else 0.3, verb=0.4)
for k in range(8): place(hat(), 5.5 + k * STEP * 1.0, 0.1 + 0.05 * k, pan=0.3)
for t0 in (5.625, 5.75, 5.8125, 5.875, 5.9375): place(snare(), t0, 0.28, verb=0.2)
place(whoosh(0.5), 5.5, 0.4)

# ------------------------------------------------------------ C/D: 6-10.6 s  (groove + build)
groove(6.0, 0); groove(8.5, 1)
place(riser(2.1), 8.5, 0.7)
t0 = 9.75; gap = 0.15625
while t0 < 10.6:
    place(snare(), t0, 0.3 + 0.5 * (t0 - 9.75) / 0.85, verb=0.15); gap = max(0.03, gap * 0.82); t0 += gap
place(whoosh(0.6), 6.4, 0.5); place(whoosh(0.4), 7.5, 0.5); place(whoosh(0.5), 9.4, 0.5); place(whoosh(0.5), 10.1, 0.6)
# the stop: silence 10.6-11.0 apart from a deep sub swell
tt = T(0.4); place(np.sin(2 * np.pi * 30 * tt) * (tt / 0.4) ** 2 * 0.5, 10.6, 1.0)

# ------------------------------------------------------------ E: 11-15 s  (the drop)
place(boom(3.5), 11.0, 1.15, verb=0.3)
place(kick(), 11.0, 1.0); place(clap(), 11.0, 0.7, verb=0.4)
words = [(11.0, F1), (11.625, F1), (12.25, Ab1), (12.875, C2)]
for t0, f in words:
    place(bass(f, 3 * STEP + 0.1), t0, 1.0)
    place(stab(Fm if f != Ab1 else [207.7, 261.6, 311.1]), t0, 0.9, verb=0.35)
    place(kick(), t0, 0.7); place(clap(), t0 + 0.0, 0.5, verb=0.3)
groove_bar = 13.5
for s in (4, 12): place(clap(), sx(11.0, s), 0.45, verb=0.3)
for s in range(0, 16, 2): place(hat(), sx(11.0, s), 0.4, pan=0.3 if (s // 2) % 2 else -0.3)
for s in (6, 10): place(kick(), sx(11.0, s), 0.9)
for k, (s, f) in enumerate([(0, F4), (3, Ab4), (6, C5), (8, Ab4), (11, Eb5), (14, C5)]):
    place(pluck(f), sx(11.0, s) + 0.0, 0.35, pan=-0.4 if k % 2 else 0.4, verb=0.3)
groove(13.5, 0, arp=True)
place(bass(F1, 1.1), 14.4, 1.0)                    # long tail 808 into the final hold
place(riser(0.6), 14.4, 0.0)

# ------------------------------------------------------------ master
def conv(x, ir):
    n = len(x) + len(ir); nf = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, nf) * np.fft.rfft(ir, nf), nf)[:len(x)]
ti = T(1.4)
irL = hp(rng.normal(size=len(ti))) * np.exp(-ti * 3.6) * np.minimum(ti / 0.01, 1)
irR = hp(rng.normal(size=len(ti))) * np.exp(-ti * 3.6) * np.minimum(ti / 0.01, 1)
irL /= np.abs(irL).sum() / 12; irR /= np.abs(irR).sum() / 12
L += 0.28 * conv(VL, irL); R += 0.28 * conv(VR, irR)

# slow pre-drop duck: silence between 10.6 and 11.0 for everything except the sub swell
duck = np.ones(N); i0, i1 = int(10.6 * SR), int(11.0 * SR)
duck[i0:i1] = np.linspace(0.12, 0.0, i1 - i0) ** 1
# (the sub swell is added after the duck, so rebuild it)
L *= duck; R *= duck
tt = T(0.4); sub = np.sin(2 * np.pi * 30 * tt) * (tt / 0.4) ** 2 * 0.5
L[i0:i1] += sub; R[i0:i1] += sub

m = max(np.abs(L).max(), np.abs(R).max())
L, R = np.tanh(1.25 * L / m) / np.tanh(1.25), np.tanh(1.25 * R / m) / np.tanh(1.25)
fade = np.ones(N); fi = int(0.35 * SR); fade[-fi:] = np.linspace(1, 0, fi) ** 1.5
L *= fade * 0.92; R *= fade * 0.92

out = np.stack([L, R], 1)
pcm = (np.clip(out, -1, 1) * 32767).astype('<i2')
with wave.open(sys.argv[1] if len(sys.argv) > 1 else 'score.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print('peak', np.abs(out).max(), 'rms', np.sqrt((out ** 2).mean()))
