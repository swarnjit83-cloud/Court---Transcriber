#!/usr/bin/env python3
"""Procedural 'No Race, No Chase' reel: 1080x1920, 24 fps, 15 s. Renders at 720x1280 and upscales in ffmpeg."""
import math, subprocess, sys, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from multiprocessing import Pool
from functools import lru_cache

W, H = 720, 1280; FPS = 24; DUR = 15.0; NF = int(round(FPS * DUR))
P = 1440; HZ = 840; GY = 1010.0; VY = 590.0; HH = 470.0; V = 215.0; PC = 2800.0
FB = '/usr/share/fonts/opentype/inter/InterDisplay-Black.otf'
FI = '/usr/share/fonts/opentype/inter/InterDisplay-LightItalic.otf'

def sstep(a, b, t):
    x = min(1.0, max(0.0, (t - a) / (b - a))); return x * x * (3 - 2 * x)
def lerp(a, b, x): return a + (b - a) * x
def ev(lst, t, dec):
    return sum(a * math.exp(-(t - te) * dec) for te, a in lst if t >= te)

# ------------------------------------------------------------------ timeline helpers
def hero_x(t): return 1500.0 + V * (t - 3.0)
def hero_ph(t): return 2 * math.pi * 0.62 * (t - 3.0) + 0.5
def crate(t):
    if t < 3.0: return 1.0
    if t < 3.6: return lerp(1.0, 0.10, sstep(3.0, 3.6, t))
    if t < 8.0: return 0.10
    if t < 8.4: return lerp(0.10, 1.6, sstep(8.0, 8.4, t))
    if t < 10.7: return 1.6
    if t < 11.0: return 1.0
    return 1.2
TS = np.arange(0, 15.5, 1 / 480.0)
CPH = np.concatenate([[0], np.cumsum(np.array([crate(x) for x in TS[:-1]]) / 480.0)])
def cphase(t): return float(np.interp(t, TS, CPH))

CUT_T = [0.45, 0.9, 1.4, 1.95, 2.5]
SHAKE_EV = [(0.0, 8), (0.45, 12), (0.9, 12), (1.4, 12), (1.95, 12), (2.5, 14), (3.0, 34), (6.0, 6), (6.45, 14), (6.9, 8),
            (7.5, 8), (8.0, 14), (9.4, 10), (10.2, 12), (11.0, 40), (11.625, 22), (12.25, 22), (12.875, 26)]
CA_EV = [(0.0, 7), (0.45, 7), (0.9, 7), (1.4, 7), (1.95, 7), (2.5, 8), (3.0, 14), (6.45, 10), (8.0, 9), (9.4, 6), (10.2, 8),
         (11.0, 20), (11.625, 10), (12.25, 10), (12.875, 12)]
FLASH_EV = [(3.0, 0.85, 9), (6.45, 0.30, 12), (8.0, 0.22, 10), (11.0, 1.0, 6), (11.625, 0.22, 12), (12.25, 0.22, 12), (12.875, 0.30, 10)]

def pose(h, ph, run):
    A = 0.95 if run else 0.42; K = 1.55 if run else 0.6; lean = 0.30 if run else 0.05
    th = 0.25 * h; sh = 0.25 * h; legs = []
    for phi in (ph, ph + math.pi):
        a = A * math.sin(phi); kn = K * (0.12 + 0.88 * max(0.0, math.cos(phi)))
        kx, ky = th * math.sin(a), th * math.cos(a); b = a - kn
        legs.append(((kx, ky), (kx + sh * math.sin(b), ky + sh * math.cos(b))))
    low = max(l[1][1] for l in legs); foot = 0.035 * h
    hipy = -(low + foot)
    if run: hipy -= 0.035 * h * abs(math.sin(ph))
    u = (math.sin(lean), -math.cos(lean)); n = (math.cos(lean), math.sin(lean))
    S0 = (0.33 * h * u[0], 0.33 * h * u[1]); R = 0.062 * h
    N = (S0[0] + 0.045 * h * u[0], S0[1] + 0.045 * h * u[1])
    C = (N[0] + 1.05 * R * math.sin(lean * 1.2), N[1] - 1.05 * R * math.cos(lean * 1.2))
    return dict(A=A, K=K, lean=lean, legs=legs, hipy=hipy, u=u, n=n, S0=S0, N=N, C=C, R=R, foot=foot)

HERO = dict(jacket=(206, 188, 152), tee=(18, 18, 24), pants=(40, 42, 58), shoe=(246, 246, 250), skin=(200, 148, 114),
            hair=(16, 13, 18))

def figure(d, S, x, gy, h, ph, run, pal, face=1, flip=False, a=255, hero=False, gl=0.0, smile=0.0, prop=0):
    ps = pose(h, ph, run); hipy = ps['hipy']
    def Tp(lx, ly):
        X = x + face * lx; Y = gy + hipy + ly
        if flip: Y = 2 * gy - Y
        return (X * S, Y * S)
    def col(c, k=1.0): return (min(255, int(c[0] * k)), min(255, int(c[1] * k)), min(255, int(c[2] * k)), a)
    def limb(p, q, w, c):
        d.line([p, q], fill=c, width=max(1, int(w * S)))
        r = w * S / 2
        for c0 in (p, q): d.ellipse([c0[0] - r, c0[1] - r, c0[0] + r, c0[1] + r], fill=c)
    def disc(p, r, c): d.ellipse([p[0] - r * S, p[1] - r * S, p[0] + r * S, p[1] + r * S], fill=c)
    jac = pal['jacket']; pan = pal['pants']; shoe = pal['shoe']; skin = pal['skin']
    dk = 0.7
    ua = 0.17 * h; fa = 0.17 * h
    Aa = 1.0 * ps['A'] if run else 1.05 * ps['A']; bend = 1.45 if run else 0.35
    def arm(sign, far):
        ang = sign * Aa * math.sin(ph); S0 = ps['S0']
        el = (S0[0] + ua * math.sin(ang), S0[1] + ua * math.cos(ang)); b = ang + bend
        hd = (el[0] + fa * math.sin(b), el[1] + fa * math.cos(b)); k = dk if far else 1.0
        limb(Tp(*S0), Tp(*el), (0.075 if hero else 0.056) * h, col(jac, k))
        limb(Tp(*el), Tp(*hd), (0.063 if hero else 0.048) * h, col(jac, k))
        disc(Tp(*hd), 0.03 * h, col(skin, k))
        if prop == 2 and not far:
            q = Tp(hd[0], hd[1] + 0.05 * h); d.rectangle([q[0] - .05 * h * S, q[1] - .035 * h * S, q[0] + .05 * h * S, q[1] + .035 * h * S], fill=col(jac, .8)) if not flip else None
    def leg(i, far):
        k, an = ps['legs'][i]; kc = dk if far else 1.0
        limb(Tp(0, 0), Tp(*k), 0.082 * h, col(pan, kc)); limb(Tp(*k), Tp(*an), 0.064 * h, col(pan, kc))
        limb(Tp(an[0], an[1] + 0.012 * h), Tp(an[0] + 0.075 * h, an[1] + 0.02 * h), ps['foot'] * 1.9, col(shoe, kc))
        if hero: limb(Tp(an[0] - 0.01 * h, an[1] + 0.034 * h), Tp(an[0] + 0.08 * h, an[1] + 0.036 * h), ps['foot'] * 0.45, col((120, 120, 128), kc))
    arm(+1, True); leg(1, True); leg(0, False)
    u, n, S0 = ps['u'], ps['n'], ps['S0']
    wh, ws = (0.088 * h, 0.104 * h) if hero else (0.062 * h, 0.075 * h)
    if prop == 1:
        c = (0.19 * h * u[0] - n[0] * 0.13 * h, 0.19 * h * u[1] - n[1] * 0.13 * h)
        pts = [Tp(c[0] + sx_ * u[0] * 0.13 * h + sy_ * n[0] * 0.05 * h, c[1] + sx_ * u[1] * 0.13 * h + sy_ * n[1] * 0.05 * h) for sx_, sy_ in ((1, 1), (1, -1), (-1, -1), (-1, 1))]
        d.polygon(pts, fill=col(jac, .8))
    d.polygon([Tp(n[0] * wh, n[1] * wh), Tp(S0[0] + n[0] * ws, S0[1] + n[1] * ws), Tp(S0[0] - n[0] * ws, S0[1] - n[1] * ws), Tp(-n[0] * wh, -n[1] * wh)], fill=col(jac))
    disc(Tp(*S0), ws / h * h * 0.98, col(jac))
    if hero:
        hem = (0.05 * h * u[0], 0.05 * h * u[1])
        d.polygon([Tp(n[0] * wh * 1.04, n[1] * wh * 1.04), Tp(hem[0] + n[0] * wh * 1.04, hem[1] + n[1] * wh * 1.04), Tp(hem[0] - n[0] * wh * 1.04, hem[1] - n[1] * wh * 1.04), Tp(-n[0] * wh * 1.04, -n[1] * wh * 1.04)], fill=col(jac, .78))
        # centre zip + chest highlight
        d.line([Tp(*S0), Tp(0, 0)], fill=col(jac, .8), width=max(1, int(2.2 * S)))
        disc(Tp(ps['N'][0] - 0.004 * h, ps['N'][1] + 0.005 * h), 0.046 * h, col(pal['tee']))
    C = ps['C']; R = ps['R']
    limb(Tp(*S0), Tp(*ps['N']), 0.05 * h, col(skin))
    disc(Tp(*C), R, col(skin))
    if hero:
        sk = pal['skin']
        disc(Tp(C[0] - .3 * R, C[1] - .42 * R), .8 * R, col(pal['hair']))
        
        disc(Tp(C[0] + .05 * R, C[1] - .8 * R), .6 * R, col(pal['hair']))
        d.polygon([Tp(C[0] + .88 * R, C[1] + .0), Tp(C[0] + 1.2 * R, C[1] + .3 * R), Tp(C[0] + .9 * R, C[1] + .38 * R)], fill=col(sk))
        disc(Tp(C[0] - .2 * R, C[1] + .1 * R), .2 * R, col(sk, .82))
        gy_ = lerp(C[1] - .72 * R, C[1] - .05 * R, gl)
        p0 = Tp(C[0] + .0 * R, gy_); p1 = Tp(C[0] + 1.14 * R, gy_ + .34 * R)
        d.rounded_rectangle([min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1])], radius=int(.1 * R * S), fill=(8, 8, 12, a))
        gp = Tp(C[0] + .45 * R, gy_ + .05 * R); gq = Tp(C[0] + .75 * R, gy_ + .02 * R)
        d.line([gp, gq], fill=(255, 255, 255, int(a * .75)), width=max(1, int(2 * S)))
        d.line([Tp(C[0] + .0 * R, gy_ + .12 * R), Tp(C[0] - .7 * R, gy_ + .1 * R)], fill=(8, 8, 12, a), width=max(1, int(.07 * R * S)))
        # half-smile
        m0 = Tp(C[0] + .5 * R, C[1] + .58 * R); m1 = Tp(C[0] + .98 * R, C[1] + (.58 - .16 * smile) * R)
        d.line([m0, m1], fill=col(sk, .55), width=max(1, int(.06 * R * S)))
        # chain
        cc = Tp(S0[0] + .02 * h, S0[1] + .045 * h)
        d.arc([cc[0] - .075 * h * S, cc[1] - .06 * h * S, cc[0] + .075 * h * S, cc[1] + .07 * h * S], 200, 340, fill=(215, 220, 232, a), width=max(1, int(.012 * h * S)))
        disc((cc[0] / S + .0, cc[1] / S + .07 * h), .014 * h, (215, 220, 232, a)) if False else None
    arm(-1, False)

# ------------------------------------------------------------------ static world
def wrap_rect(d, x0, y0, x1, y1, fill):
    for o in (-P, 0, P): d.rectangle([x0 + o, y0, x1 + o, y1], fill=fill)
def grad(stops, n):
    xs = np.linspace(0, 1, n); out = np.zeros((n, 3))
    for c in range(3): out[:, c] = np.interp(xs, [s[0] for s in stops], [s[1][c] for s in stops])
    return out

def build_world():
    rng = np.random.default_rng(3)
    # sky
    col = grad([(0, (8, 24, 62)), (0.45, (28, 76, 124)), (0.72, (222, 124, 104)), (0.9, (255, 176, 100)), (1, (255, 205, 140))], HZ + 60)
    sky = np.zeros((H, P, 3)); sky[:HZ + 60] = col[:, None, :]; sky[HZ + 60:] = col[-1]
    yy, xx = np.mgrid[0:H, 0:P]
    glow = np.exp(-(((xx - P / 2) / 280.0) ** 2 + ((yy - (HZ - 30)) / 170.0) ** 2))[..., None]
    sky = sky + glow * np.array([255, 160, 80]) * 0.55
    skyim = Image.fromarray(np.clip(sky, 0, 255).astype('uint8')).convert('RGBA')
    cl = Image.new('RGBA', (P, H), (0, 0, 0, 0)); dc = ImageDraw.Draw(cl)
    for _ in range(9):
        cx, cy = rng.uniform(0, P), rng.uniform(280, 640); rx, ry = rng.uniform(200, 420), rng.uniform(14, 34)
        for o in (-P, 0, P): dc.ellipse([cx - rx + o, cy - ry, cx + rx + o, cy + ry], fill=(255, 150, 130, 70))
    skyim = Image.alpha_composite(skyim, cl.filter(ImageFilter.GaussianBlur(14)))
    # building layers
    def skyline(seed, wr, hr, base, colr, win_p, glow_signs, y_top_min=0):
        r = np.random.default_rng(seed); im = Image.new('RGBA', (P, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        gl = Image.new('RGBA', (P, H), (0, 0, 0, 0)); dg = ImageDraw.Draw(gl); x = 0
        while x < P:
            w = int(r.uniform(*wr)); h = int(r.uniform(*hr)); top = max(y_top_min, base - h)
            c = tuple(int(v * r.uniform(.85, 1.15)) for v in colr)
            wrap_rect(d, x, top, x + w, base + 60, c + (255,))
            wrap_rect(d, x, top, x + 3, base + 60, tuple(min(255, int(v * 1.5 + 8)) for v in c) + (255,))
            for wx in range(x + 8, x + w - 12, 15):
                for wy in range(top + 14, base - 10, 24):
                    if r.random() < win_p:
                        wc = (255, 206, 120) if r.random() < .78 else ((120, 224, 255) if r.random() < .6 else (255, 110, 190))
                        wrap_rect(d, wx, wy, wx + 8, wy + 12, wc + (255,))
                        for o in (-P, 0, P): dg.rectangle([wx + o - 2, wy - 2, wx + o + 10, wy + 14], fill=wc + (110,))
            if glow_signs and r.random() < .5:
                sc = [(255, 60, 160), (40, 220, 255), (255, 200, 40)][int(r.integers(0, 3))]; sy_ = int(r.uniform(top + 40, base - 160)); sw = int(r.uniform(14, 22))
                sx_ = x + int(r.uniform(6, max(8, w - sw - 6)))
                for o in (-P, 0, P):
                    dg.rectangle([sx_ + o, sy_, sx_ + sw + o, sy_ + int(r.uniform(90, 210))], fill=sc + (230,))
                    d.rectangle([sx_ + o + 3, sy_ + 3, sx_ + sw + o - 3, sy_ + 80], fill=(255, 255, 255, 255))
            x += w + int(r.uniform(0, 8))
        g2 = gl.filter(ImageFilter.GaussianBlur(10)); g2.putalpha(g2.getchannel('A').point(lambda v: min(255, int(v * 1.6))))
        return Image.alpha_composite(Image.alpha_composite(im, g2), gl.filter(ImageFilter.GaussianBlur(1.5)))
    far = skyline(5, (50, 110), (160, 440), HZ, (70, 66, 112), .05, False)
    far.putalpha(far.getchannel('A').point(lambda v: int(v * .9)))
    mid = skyline(8, (70, 150), (330, 800), HZ, (28, 28, 58), .20, True)
    # near slabs
    near = Image.new('RGBA', (P, H), (0, 0, 0, 0)); dn = ImageDraw.Draw(near); r = np.random.default_rng(21); gln = Image.new('RGBA', (P, H), (0, 0, 0, 0)); dgn = ImageDraw.Draw(gln)
    for sx0 in (60, 460, 880, 1200):
        w = int(r.uniform(200, 300)); top = int(r.uniform(-40, 220)); sx_ = sx0 + int(r.uniform(-30, 30))
        wrap_rect(dn, sx_, top, sx_ + w, HZ + 40, (12, 13, 28, 255)); wrap_rect(dn, sx_, top, sx_ + 4, HZ + 40, (60, 52, 84, 255))
        for wx in range(sx_ + 14, sx_ + w - 20, 22):
            for wy in range(top + 24, HZ - 20, 34):
                if r.random() < .16:
                    wc = (255, 190, 110) if r.random() < .75 else (130, 220, 255)
                    wrap_rect(dn, wx, wy, wx + 12, wy + 18, wc + (255,))
                    for o in (-P, 0, P): dgn.rectangle([wx + o - 3, wy - 3, wx + o + 15, wy + 21], fill=wc + (90,))
    for lx in (330, 760, 1100):         # lamp posts
        for o in (-P, 0, P):
            dn.rectangle([lx + o, 520, lx + o + 6, HZ + 10], fill=(10, 10, 18, 255)); dn.rectangle([lx + o - 22, 514, lx + o + 6, 522], fill=(10, 10, 18, 255))
            dgn.ellipse([lx + o - 40, 500, lx + o - 8, 532], fill=(255, 200, 120, 255))
    g3 = gln.filter(ImageFilter.GaussianBlur(14)); near = Image.alpha_composite(Image.alpha_composite(near, g3), gln.filter(ImageFilter.GaussianBlur(1)))
    # street
    st = Image.new('RGBA', (P, H), (0, 0, 0, 0)); s_ = np.zeros((H - HZ, P, 4), np.uint8)
    cg = grad([(0, (62, 48, 66)), (.25, (30, 28, 44)), (1, (8, 8, 14))], H - HZ)
    s_[..., :3] = cg[:, None, :].astype('uint8'); s_[..., 3] = 255
    st = Image.fromarray(s_, 'RGBA'); full = Image.new('RGBA', (P, H), (0, 0, 0, 0)); full.paste(st, (0, HZ))
    d = ImageDraw.Draw(full); r = np.random.default_rng(31)
    d.rectangle([0, HZ - 8, P, HZ + 4], fill=(78, 72, 98, 255))
    for x in range(0, P, 120):          # crosswalk
        d.polygon([(x + 20, 892), (x + 54, 892), (x + 82, H), (x + 6, H)], fill=(222, 222, 228, 140))
    ref = Image.new('RGBA', (P, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(ref)
    for _ in range(26):
        c = [(255, 170, 90), (255, 70, 170), (60, 220, 255), (255, 210, 120)][int(r.integers(0, 4))]; x = r.uniform(0, P); w = r.uniform(8, 30); l = r.uniform(80, 340)
        for o in (-P, 0, P): dr.rectangle([x + o, HZ + 6, x + o + w, HZ + l], fill=c + (int(r.uniform(60, 120)),))
    for o in (-P, 0, P): dr.polygon([(P / 2 - 40 + o, HZ + 6), (P / 2 + 40 + o, HZ + 6), (P / 2 + 130 + o, HZ + 420), (P / 2 - 130 + o, HZ + 420)], fill=(255, 160, 90, 85))
    for _ in range(14):
        x, y = r.uniform(0, P), r.uniform(950, 1230); rx = r.uniform(110, 260); ry = r.uniform(14, 30)
        for o in (-P, 0, P): dr.ellipse([x - rx + o, y - ry, x + rx + o, y + ry], fill=(255, 205, 160, 34))
    ref = ref.filter(ImageFilter.GaussianBlur(5)); full = Image.alpha_composite(full, ref)
    def strip(im): s = Image.new('RGBA', (3 * P, H)); [s.paste(im, (k * P, 0)) for k in range(3)]; return s
    return [strip(skyim), strip(far), strip(mid), strip(near), strip(full)]

LAYERS = None
FACT = [0.04, 0.22, 0.55, 1.0, 1.0]

def crop(strip, f, camx, cy, z):
    cx = camx * f; cxm = P + (cx % P); l = cxm - W / (2 * z); t = cy - H / (2 * z)
    return strip.resize((W, H), Image.BILINEAR, box=(l, t, l + W / z, t + H / z))

# ------------------------------------------------------------------ crowd
rr = np.random.default_rng(11)
RUN = []
for _ in range(36):
    gy = rr.uniform(895, 1190); sd = (gy - VY) / (GY - VY)
    RUN.append(dict(x0=rr.uniform(0, PC), gy=gy, d=int(rr.choice([-1, 1], p=[.6, .4])), v=rr.uniform(650, 1000) * sd ** 0.7, ph=rr.uniform(0, 6.28),
                    prop=int(rr.integers(0, 3)), hs=rr.uniform(.93, 1.1),
                    col=[(24, 26, 46), (32, 26, 50), (18, 32, 48), (52, 24, 38), (28, 36, 64), (58, 44, 34)][int(rr.integers(0, 6))]))
def runner_pal(c): return dict(jacket=c, pants=tuple(int(v * .85) for v in c), shoe=tuple(int(v * .7) for v in c), skin=tuple(int(v * 1.12) for v in c), hair=c, tee=c)

def draw_crowd(img, items, t, camx, cy, z, refl=None, hero_gy=GY, front=False):
    d = ImageDraw.Draw(img, 'RGBA'); rate = crate(t); n = 1 + int(min(5, rate * 4))
    items = sorted(items, key=lambda r: r['gy'])
    for r in items:
        sd = (r['gy'] - VY) / (GY - VY); h = HH * sd * r['hs'] * z; sy = (r['gy'] - cy) * z + H / 2
        pal = runner_pal(r['col'])
        for k in range(n - 1, -1, -1):
            tk = t - k * 0.012; cp = cphase(tk)
            wx = (r['x0'] + r['d'] * r['v'] * cp) % PC; rel = ((wx - camx + PC / 2) % PC) - PC / 2; sx = rel * z + W / 2
            if sx < -h or sx > W + h: break
            al = 255 if k == 0 else int(255 * 0.30 * (1 - k / (n + 1)))
            ph = 2 * math.pi * 2.4 * cp + r['ph']
            figure(d, 1, sx, sy, h, ph, True, pal, face=r['d'], a=al, prop=r['prop'])
            if k == 0 and refl is not None:
                figure(ImageDraw.Draw(refl, 'RGBA'), 1, sx, sy, h, ph, True, pal, face=r['d'], flip=True, a=120, prop=r['prop'])

def shiftA(a, dx, dy):
    out = np.zeros_like(a); h_, w_ = a.shape
    ys, yd = (slice(dy, h_), slice(0, h_ - dy)) if dy >= 0 else (slice(0, h_ + dy), slice(-dy, h_))
    xs, xd = (slice(dx, w_), slice(0, w_ - dx)) if dx >= 0 else (slice(0, w_ + dx), slice(-dx, w_))
    out[ys, xs] = a[yd, xd]; return out
def add_rim(layer, rw, color, strength):
    a = np.asarray(layer.getchannel('A'), np.float32) / 255
    edge = np.clip(a - shiftA(a, -rw, int(rw * .6)), 0, 1) * strength
    e = Image.fromarray((edge * 255).astype('uint8')).filter(ImageFilter.GaussianBlur(1.0))
    rim = Image.new('RGBA', layer.size, color + (0,)); rim.putalpha(Image.fromarray((np.asarray(e, np.float32) * (a > 0.05)).astype('uint8')))
    return Image.alpha_composite(layer, rim)

# ------------------------------------------------------------------ text
@lru_cache(maxsize=None)
def font(path, size): return ImageFont.truetype(path, size)
def put_text(img, txt, cx, cy, size, fill, alpha=1.0, scale=1.0, glow=None, glow_k=1.0, stroke=0, path=FB, maxw=660, jit=(0, 0), shadow=True):
    if alpha <= 0.01: return
    f = font(path, max(8, int(size * scale)))
    wlen = f.getlength(txt)
    if wlen > maxw * max(scale, 1.0): f = font(path, max(8, int(size * scale * maxw * max(scale, 1.0) / wlen)))
    x, y = cx + jit[0], cy + jit[1]
    tmp = Image.new('RGBA', img.size, (0, 0, 0, 0)); dt = ImageDraw.Draw(tmp)
    dt.text((x, y), txt, font=f, fill=(255, 255, 255, 255), anchor='mm', stroke_width=stroke, stroke_fill=(255, 255, 255, 255))
    A = tmp.getchannel('A')
    if shadow:
        sh = Image.new('RGBA', img.size, (0, 0, 0, 0)); sh.putalpha(A.filter(ImageFilter.GaussianBlur(7)).point(lambda v: int(v * .7 * alpha))); sh = sh.transform(img.size, Image.AFFINE, (1, 0, 0, 0, 1, -8)); img.alpha_composite(sh)
    if glow:
        g = Image.new('RGBA', img.size, glow + (0,)); g.putalpha(A.filter(ImageFilter.GaussianBlur(20)).point(lambda v: min(255, int(v * 1.9 * glow_k * alpha)))); img.alpha_composite(g)
    if stroke:
        o = Image.new('RGBA', img.size, (0, 0, 0, 0)); d2 = ImageDraw.Draw(o)
        d2.text((x, y), txt, font=f, fill=(0, 0, 0, int(255 * alpha)), anchor='mm', stroke_width=stroke + 3, stroke_fill=(0, 0, 0, int(255 * alpha))); img.alpha_composite(o)
    c = Image.new('RGBA', img.size, fill + (0,)); mask = Image.new('L', img.size, 0); ImageDraw.Draw(mask).text((x, y), txt, font=f, fill=int(255 * alpha), anchor='mm'); c.putalpha(mask); img.alpha_composite(c)

# ------------------------------------------------------------------ numeric post
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
RV = np.sqrt(((XX - W / 2) / (W / 2)) ** 2 + ((YY - H / 2) / (H / 2)) ** 2) / 1.25
VIG = (1 - 0.55 * np.clip(RV, 0, 1.4) ** 2.2)[..., None].astype(np.float32)
RAYM = None
def build_rays():
    im = Image.new('L', (3 * W, H), 0); d = ImageDraw.Draw(im); c = 1.5 * W
    for off, w0, w1 in ((0, 22, 250), (-80, 10, 120), (95, 12, 150)):
        d.polygon([(c + off - w0, 0), (c + off + w0, 0), (c + off + w1, 1100), (c + off - w1, 1100)], fill=255)
    im = im.filter(ImageFilter.GaussianBlur(26)); a = np.asarray(im, np.float32) / 255
    return a * ((1 - np.minimum(np.arange(H), 1200) / 1200.0) ** 1.4)[:, None]

def add_glow(a, cx, cy, rx, ry, color, s):
    x0, x1 = int(max(0, cx - 3 * rx)), int(min(W, cx + 3 * rx)); y0, y1 = int(max(0, cy - 3 * ry)), int(min(H, cy + 3 * ry))
    if x1 <= x0 or y1 <= y0: return
    g = np.exp(-(((XX[y0:y1, x0:x1] - cx) / rx) ** 2 + ((YY[y0:y1, x0:x1] - cy) / ry) ** 2))[..., None]
    a[y0:y1, x0:x1] += g * (np.array(color, np.float32) / 255) * s

def grade(a):
    lum = a.mean(2, keepdims=True)
    a = a + np.array([-0.02, 0.035, 0.065], np.float32) * (1 - lum) ** 2 * 1.2 + np.array([0.07, 0.025, -0.045], np.float32) * lum ** 2 * 1.2
    a = np.clip(a * 1.05, 0, 1); a = a * a * (3 - 2 * a) * 0.55 + a * 0.45
    g = a.mean(2, keepdims=True); return np.clip(g + (a - g) * 1.2, 0, 1)
def bloom(a):
    br = np.clip(a - 0.78, 0, 1)
    im = Image.fromarray((br * 255).astype('uint8')).resize((W // 2, H // 2), Image.BILINEAR).filter(ImageFilter.GaussianBlur(11)).resize((W, H), Image.BILINEAR)
    im2 = Image.fromarray((br * 255).astype('uint8')).resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(9)).resize((W, H), Image.BILINEAR)
    return a + (np.asarray(im, np.float32) + np.asarray(im2, np.float32)) / 255 * 0.85

# ------------------------------------------------------------------ strikes
STRIKES = [3.0 + (math.pi / 2 + k * math.pi - 0.5) / (2 * math.pi * 0.62) for k in range(0, 16)]
STRIKES = [s for s in STRIKES if s >= 3.0]

# ------------------------------------------------------------------ camera
def camera(t):
    """returns camx, cy, z, rot, bgblur"""
    hx = hero_x(t); hh = HH
    if t < 3.0:
        shots = [(0.0, .45, 1500, 900, 640, 1.0, 1.08, 0), (.45, .9, 2600, -700, 1000, 2.3, 2.3, 0), (.9, 1.4, 400, 1000, 760, 1.5, 1.6, 0),
                 (1.4, 1.95, 3300, -800, 700, 2.8, 2.9, -2.0), (1.95, 2.5, 900, 1200, 700, 1.2, 1.25, 2.0), (2.5, 3.0, 2000, 300, 640, 1.0, 1.9, 0)]
        for a, b, cx0, spd, cy, z0, z1, rot in shots:
            if t < b:
                u = (t - a) / (b - a); return cx0 + spd * (t - a), cy, lerp(z0, z1, u), rot * (0.5 + u * .5), 0.0
    if t < 6.0:
        u = sstep(3.0, 6.0, t); off = 440 * (1 - u)
        return hx + off, lerp(640, 700, u), lerp(1.0, 1.2, u), 0.0, 0.0
    if t < 6.9:
        u = (t - 6.0) / 0.9; return hx + 25, 580 + 10 * u, lerp(3.2, 3.7, u), lerp(2, -1.5, u), 5.0
    if t < 7.5:
        u = (t - 6.9) / 0.6; return hx + 30 + 20 * u, GY - 110, lerp(2.8, 3.1, u), lerp(-2, 1, u), 4.0
    if t < 8.0:
        u = (t - 7.5) / 0.5; return hx + 10 + 20 * u, GY - 360, lerp(2.2, 2.45, u), lerp(1.5, 0, u), 4.0
    if t < 9.4:
        u = (t - 8.0) / 1.4; return hx + lerp(-170, 190, u), GY - 255, lerp(1.45, 1.8, u), lerp(-1, 3, u), 2.2
    if t < 10.2:
        u = (t - 9.4) / 0.8; return hx + 150 + 30 * math.sin(u * 3), GY - 335, lerp(1.9, 2.1, u), lerp(-3, -1, u), 3.0
    if t < 11.0:
        u = sstep(10.2, 10.75, t); return hx + lerp(60, 20, u), lerp(700, 640, u), lerp(2.3, 1.0, u), lerp(2, 0, u), 0.0
    u = (t - 11.0) / 4.0; return hx + 0.0, 640, 1.0 + 0.05 * u, 0.0, 0.0

WORDS = [("NO RACE.", 232, 150, (255, 255, 255), (0, 190, 255), 11.0),
         ("NO CHASE.", 372, 136, (255, 255, 255), (255, 50, 150), 11.625),
         ("I'M WINNING", 508, 112, (255, 214, 0), (255, 110, 0), 12.25),
         ("AT MY PACE.", 614, 112, (255, 214, 0), (255, 110, 0), 12.875)]

def render_frame(i):
    t = i / FPS; rng = np.random.default_rng(1000 + i)
    camx, cy, z, rot, bgb = camera(t)
    sh = ev(SHAKE_EV, t, 11.0) + 2.2
    ph_ = t * 40; camx += sh * (math.sin(ph_ * 1.3) + .6 * math.sin(ph_ * 2.9 + 1)) * .6; cy += sh * (math.sin(ph_ * 1.7 + 2) + .6 * math.sin(ph_ * 3.3)) * .5
    ca = ev(CA_EV, t, 12.0)
    zc = z * (math.cos(math.radians(abs(rot))) + (H / W) * math.sin(math.radians(abs(rot)))) if rot else z
    cy = min(max(cy, H / (2 * zc)), H - H / (2 * zc)); z = zc
    # background
    base = crop(LAYERS[0], FACT[0], camx, cy, z).convert('RGBA')
    for k in (1, 2, 3, 4): base = Image.alpha_composite(base, crop(LAYERS[k], FACT[k], camx, cy, z))
    if bgb > 0: base = base.filter(ImageFilter.GaussianBlur(bgb * min(1.0, z / 2.0 + .3)))
    hero_on = t >= 3.0 - 0.01
    inE = t >= 11.0
    hs = 0.8 if inE else 1.0; hgy = 1060.0 if inE else GY
    # actors
    refl = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    back = [r for r in RUN if r['gy'] <= hgy] if hero_on else RUN; front = [r for r in RUN if r['gy'] > hgy] if hero_on else []
    if 3.2 < t < 8.0: front = []
    cb = Image.new('RGBA', (W, H), (0, 0, 0, 0)); cf = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw_crowd(cb, back, t, camx, cy, z, refl=refl)
    if front: draw_crowd(cf, front, t, camx, cy, z, refl=refl)
    hero = None; hsx = hsy = 0
    if hero_on:
        hh = HH * hs * z; hsx = (hero_x(t) - camx) * z + W / 2; hsy = (hgy - cy) * z + H / 2
        gl = sstep(6.45, 6.62, t); sm = 0.35 + 0.65 * sstep(7.0, 7.6, t)
        L2 = Image.new('RGBA', (W * 2, H * 2), (0, 0, 0, 0))
        figure(ImageDraw.Draw(L2, 'RGBA'), 2, hsx, hsy, hh, hero_ph(t), False, HERO, hero=True, gl=gl, smile=sm)
        hero = L2.reduce(2)
        hero = add_rim(hero, max(2, int(2 + z * .8)), (255, 196, 120), .9)
        figure(ImageDraw.Draw(refl, 'RGBA'), 1, hsx, hsy, hh, hero_ph(t), False, HERO, flip=True, a=120, hero=True, gl=gl)
    refl = refl.filter(ImageFilter.GaussianBlur(3 + z))
    ra = refl.getchannel('A').point(lambda v: int(v * .42)); refl.putalpha(ra)
    # puddle ripples + droplets (6.2 - 8.6)
    fx = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dfx = ImageDraw.Draw(fx, 'RGBA')
    if 6.0 <= t <= 8.6 and hero_on:
        for k, ts in enumerate(STRIKES):
            age = t - ts
            if 0 <= age < 0.9:
                xw = hero_x(ts) + 95; sx = (xw - camx) * z + W / 2; sy = (GY - 6 - cy) * z + H / 2
                for dl in (0, .13):
                    a2 = age - dl
                    if a2 > 0:
                        r_ = (24 + 300 * a2) * z; dfx.ellipse([sx - r_, sy - r_ * .2, sx + r_, sy + r_ * .2], outline=(225, 240, 255, int(190 * (1 - a2 / .9))), width=max(2, int(3 * z / 2)))
                rs = np.random.default_rng(int(ts * 1000))
                for _ in range(14):
                    ang = -rs.uniform(.35, 2.8); sp = rs.uniform(180, 520)
                    px = sx + math.cos(ang) * sp * age * z; py = sy + (math.sin(ang) * sp * age + 900 * age * age / 2) * z
                    rd = max(1.5, rs.uniform(1.8, 3.8) * z ** .6)
                    if age < .7: dfx.ellipse([px - rd, py - rd, px + rd, py + rd], fill=(235, 245, 255, int(230 * (1 - age / .7))))
    # compose
    sc = Image.alpha_composite(base, refl)
    if bgb > 0:
        cb = cb.filter(ImageFilter.GaussianBlur(bgb * .8)); cf = cf.filter(ImageFilter.GaussianBlur(bgb * 1.3))
    cb = add_rim(cb, 3, (255, 150, 100), .55); cf = add_rim(cf, 3, (255, 150, 100), .55) if front else cf
    sc = Image.alpha_composite(sc, cb)
    if hero is not None: sc = Image.alpha_composite(sc, hero)
    sc = Image.alpha_composite(sc, cf); sc = Image.alpha_composite(sc, fx)
    sc = sc.convert('RGB')
    if rot: sc = sc.rotate(rot, resample=Image.BILINEAR, center=(W / 2, H / 2))
    a = np.asarray(sc, np.float32) / 255
    # light shafts on hero
    if hero_on and t < 10.7 or inE:
        it = sstep(3.0, 3.9, t) * (1 - sstep(10.3, 10.65, t)) if not inE else 0.45
        sxr = int(min(max(hsx, -W), 2 * W))
        m = RAYM[:, int(1.5 * W - sxr):int(1.5 * W - sxr) + W]
        a += m[..., None] * np.array([1.0, .78, .55], np.float32) * 0.07 * it
        add_glow(a, hsx, hsy - 0.45 * HH * z * hs, 260 * z, 360 * z, (255, 180, 110), 0.035 * it)
    # flares
    if 6.45 <= t < 6.95:
        age = t - 6.45; gx = hsx + 0.00 * z; gyy = (GY - 0.94 * HH - cy) * z + H / 2 + 0.0
        add_glow(a, W / 2 + 40, gyy, 520 * (1 - age), 7 + 5 * age, (120, 210, 255), 1.4 * math.exp(-age * 7))
        add_glow(a, W / 2 + 40, gyy, 40, 40, (255, 255, 255), 1.0 * math.exp(-age * 9))
    if 11.0 <= t:
        add_glow(a, W / 2, 430, 360, 330, (255, 120, 40), 0.18 * min(1, (t - 11.0) * 4))
    # E: sunburst + darkening
    if inE:
        a *= 0.52
        im = Image.new('L', (W // 2, H // 2), 0); dd = ImageDraw.Draw(im); c0 = (W / 4, 215)
        for k in range(18):
            a0 = math.radians(k * 20 + (t - 11) * 14); a1 = a0 + math.radians(7)
            dd.polygon([c0, (c0[0] + 900 * math.cos(a0), c0[1] + 900 * math.sin(a0)), (c0[0] + 900 * math.cos(a1), c0[1] + 900 * math.sin(a1))], fill=255)
        sb = np.asarray(im.filter(ImageFilter.GaussianBlur(4)).resize((W, H), Image.BILINEAR), np.float32) / 255
        a += sb[..., None] * np.array([1.0, .55, .2], np.float32) * (0.12 + 0.05 * math.sin(t * 6)) * min(1, (t - 11) * 3) * np.clip(1.2 - RV, 0, 1)[..., None]
    a = grade(np.clip(a, 0, 1))
    # overlays: text / HUD
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov, 'RGBA')
    if t < 3.0:
        for _ in range(26):
            y0 = rng.uniform(0, H); x0 = rng.uniform(-100, W); l = rng.uniform(160, 520)
            d.line([(x0, y0), (x0 + l, y0)], fill=(255, 255, 255, int(rng.uniform(25, 85))), width=int(rng.choice([1, 2, 3])))
        jx = (int(rng.integers(-2, 3)), int(rng.integers(-2, 3)))
        out_s = 1 + 0.35 * sstep(2.85, 3.0, t); out_a = 1 - sstep(2.85, 3.0, t)
        def slam(t0, dur=.14): 
            u = (t - t0) / dur; return None if u < 0 else (1 + 1.4 * (1 - min(1, u)) ** 2, min(1, u * 3))
        s1 = slam(0.04)
        if s1: put_text(ov, "Everyone is", 360, 300, 92, (255, 255, 255), alpha=s1[1] * out_a, scale=s1[0] * out_s, glow=(0, 200, 255), glow_k=.8, stroke=5, jit=jx)
        s2 = slam(0.5)
        if s2:
            nd = (0, 0.9, 1.05, 1.2); dots = "." * sum(1 for q in nd[1:] if t >= q)
            put_text(ov, "running" + dots, 360, 402, 104, (255, 214, 40), alpha=s2[1] * out_a, scale=s2[0] * out_s, glow=(255, 90, 0), glow_k=.9, stroke=5, jit=jx)
        # clock HUD
        cx0, cy0 = 622, 118; d.ellipse([cx0 - 48, cy0 - 48, cx0 + 48, cy0 + 48], outline=(255, 255, 255, 235), width=6, fill=(0, 0, 0, 90))
        ang = t * 2 * math.pi * 1.6 - math.pi / 2
        d.line([(cx0, cy0), (cx0 + 36 * math.cos(ang), cy0 + 36 * math.sin(ang))], fill=(255, 70, 70, 255), width=5)
        d.line([(cx0, cy0), (cx0 + 22 * math.cos(ang / 12), cy0 + 22 * math.sin(ang / 12))], fill=(255, 255, 255, 255), width=5)
        for k, (tb, bx, by) in enumerate(((0.3, 78, 140), (1.05, 640, 520), (1.8, 90, 620), (2.35, 620, 760))):
            if t >= tb and t < tb + .55:
                u = (t - tb) / .12; r_ = 30 * (1 + .5 * max(0, 1 - u)) if u < 1 else 30
                d.ellipse([bx - r_, by - r_, bx + r_, by + r_], fill=(255, 40, 60, 235)); put_text(ov, "!", bx, by, 38, (255, 255, 255), shadow=False)
    if 3.4 <= t < 5.9:
        al = sstep(3.4, 3.8, t) * (1 - sstep(5.5, 5.9, t))
        put_text(ov, "...he isn't.", 360, 215, 62, (255, 255, 255), alpha=al * .95, path=FI, glow=(255, 190, 120), glow_k=.5, scale=1 + 0.03 * (t - 3.4) / 2.5)
    if inE:
        pulse = 1 + 0.035 * math.exp(-((t - 11.0) % 0.625) * 9)
        for txt, yy_, sz, fcol, gcol, ts in WORDS:
            age = t - ts
            if age < 0: continue
            sc_ = (1 + 1.1 * math.exp(-age * 17) * (1 + .25 * math.cos(age * 34))) * pulse
            al = min(1.0, age * 40)
            jit = (int(rng.integers(-3, 4) * math.exp(-age * 12)), int(rng.integers(-3, 4) * math.exp(-age * 12)))
            put_text(ov, txt, 360, yy_ + int(2 * math.sin(t * 3 + yy_)), sz, fcol, alpha=al, scale=sc_, glow=gcol, glow_k=(1.1 + .35 * math.sin(t * 5)) if ts > 12 else .9, stroke=4, maxw=650, jit=jit)
    ova = np.asarray(ov, np.float32) / 255
    a = a * (1 - ova[..., 3:4]) + ova[..., :3] * ova[..., 3:4]
    a = bloom(a)
    if ca > 0.5:
        s = int(round(ca)); a[..., 0] = np.roll(a[..., 0], s, axis=1); a[..., 2] = np.roll(a[..., 2], -s, axis=1)
    a = a * VIG
    a = a + rng.normal(0, 0.022, (H, W, 1)).astype(np.float32)
    fl = max([0.0] + [amp * math.exp(-(t - te) * dec) for te, amp, dec in FLASH_EV if t >= te])
    if fl > 0.01: a = a * (1 - fl) + fl
    fade = 0.0
    if 10.45 <= t < 11.0: fade = sstep(10.45, 10.68, t)
    if t >= 14.75: fade = sstep(14.75, 15.0, t) * 0.55
    if fade > 0: a = a * (1 - fade)
    return (np.clip(a, 0, 1) * 255).astype(np.uint8).tobytes()

def init():
    global LAYERS, RAYM
    LAYERS = build_world(); RAYM = build_rays()
LAYERS = None
init()

if __name__ == '__main__':
    args = sys.argv[1:]
    if args and args[0] == 'stills':
        outdir = args[1]; os.makedirs(outdir, exist_ok=True)
        for s in args[2:]:
            i = int(round(float(s) * FPS)); Image.frombytes('RGB', (W, H), render_frame(i)).save(f'{outdir}/f_{s}.png')
        sys.exit()
    wav, out = args[0], args[1]
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-i', wav,
                           '-vf', 'scale=1080:1920:flags=lanczos,unsharp=5:5:0.7:5:5:0.0', '-c:v', 'libx264', '-preset', 'slow', '-crf', '15', '-pix_fmt', 'yuv420p',
                           '-c:a', 'aac', '-b:a', '224k', '-t', '15', '-movflags', '+faststart', out], stdin=subprocess.PIPE)
    with Pool(4) as pool:
        for n, fr in enumerate(pool.imap(render_frame, range(NF), chunksize=2)):
            ff.stdin.write(fr)
            if n % 24 == 0: print('frame', n, flush=True)
    ff.stdin.close(); ff.wait(); print('done')
