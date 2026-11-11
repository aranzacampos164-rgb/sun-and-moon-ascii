"""
sunMoon.py  --  ASCII sun & moon drift together, fuse into an Earth-like planet, then part again.

    pip3 install numpy pygame
    python3 sunMoon.py          (Esc or close the window to quit)
"""
import math
import os
import numpy as np


COLS, ROWS = 130, 38
FONT_SIZE = 14
FPS = 30
CYCLE = 30.0
ORBIT_R = 0.235
SUN_RAD = 0.33
MOON_RAD = 0.22
EARTH_RAD = 0.31
STAR_FADE_IN = 2.5
N_STARS = 300
N_METEORS = 3
VIBRANCE = 1.30
PLANET_FADE_IN = 4.0

RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
EXTRA = ".+*@-|"
CHARS = sorted(set(RAMP + EXTRA))
CIDX = {c: i for i, c in enumerate(CHARS)}
RAMP_IDX = np.array([CIDX[c] for c in RAMP])
SPACE = CIDX[" "]


def ss(e0, e1, x):
    """smoothstep (works with reversed edges, e.g. ss(1.0, 0.82, d))"""
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def sstep(x):
    """smootherstep 0..1 (gentler start and end than smoothstep)"""
    x = min(1.0, max(0.0, x))
    return x * x * x * (x * (x * 6 - 15) + 10)


class Stars:
    def __init__(self, W, H, seed=11):
        rng = np.random.default_rng(seed)
        n = N_STARS
        self.SX = rng.uniform(-1.0, 1.0, n) * (W / H) * 0.55
        self.SY = rng.uniform(-1.0, 1.0, n) * 0.55
        self.SD = rng.uniform(0.70, 1.0, n)
        self.SF = rng.uniform(0.8, 3.2, n)
        self.SPH = rng.uniform(0, 2 * math.pi, n)
        self.sb = rng.uniform(0.2, 0.75, n) ** 1.5
        self.sb[rng.random(n) < 0.05] = 1.0
        tint = rng.random(n)
        self.scol = np.empty((n, 3), np.float32)
        for i, k in enumerate(tint):
            if k < 0.60:
                self.scol[i] = (205, 222, 255)
            elif k < 0.85:
                self.scol[i] = (150, 185, 255)
            else:
                self.scol[i] = (255, 232, 190)
        self.GS = 1.0
        self.W, self.H = W, H


def stamp_stars(stars, CW, CHh, idx, fg, L, t, amt, pmc, scol):
    """Project the stars into the char grid; bright ones get a + shaped flare."""
    ROWS_, COLS_ = idx.shape
    W, H = stars.W, stars.H
    SX, SY, SD, SF, SPH, GS, sb = stars.SX, stars.SY, stars.SD, stars.SF, stars.SPH, stars.GS, stars.sb
    d = SD
    c = ((W * 0.5 + (SX * GS / d) * H) / CW).astype(np.int32)
    r = ((H * 0.5 + (SY * GS / d) * H) / CHh).astype(np.int32)
    alpha = ss(1.0, 0.82, d) * (0.80 + 0.20 * np.sin(t * SF + SPH)) * amt
    ok = (c >= 0) & (c < COLS_) & (r >= 0) & (r < ROWS_) & (alpha > 0.04)
    if not ok.any():
        return
    ii = np.flatnonzero(ok)
    c, r = c[ii], r[ii]
    b = sb[ii] * alpha[ii] * (1 + 0.05 / d[ii])
    msk = pmc[r, c] > 0.5
    ii, c, r, b = ii[msk], c[msk], r[msk], b[msk]
    keep = b > L[r, c] * 0.7
    ii, c, r, b = ii[keep], c[keep], r[keep], b[keep]
    if len(b) == 0:
        return
    ch = np.where(b < 0.20, CIDX["."], np.where(b < 0.42, CIDX["+"], CIDX["*"]))
    idx[r, c] = ch
    fg[r, c] = scol[ii] * np.clip(0.35 + 0.9 * b, 0, 1)[:, None]
    for j in np.flatnonzero(b > 0.55)[:40]:
        cc_, rr_, bb = int(c[j]), int(r[j]), float(b[j])
        col = scol[ii[j]]
        idx[rr_, cc_] = CIDX["@"] if bb > 0.85 else CIDX["*"]
        ln = int(2 + 6 * (bb - 0.5))
        for k in range(1, ln + 1):
            a = (1 - k / (ln + 1)) * bb
            for (dr, dc, chh) in ((0, k, "-"), (0, -k, "-"),
                                  (int(k / 2) + (1 if k > 2 else 0), 0, "|"),
                                  (-(int(k / 2) + (1 if k > 2 else 0)), 0, "|")):
                r2, c2 = rr_ + dr, cc_ + dc
                if 0 <= r2 < ROWS_ and 0 <= c2 < COLS_ and pmc[r2, c2] > 0.5 and L[r2, c2] < a * 0.8:
                    idx[r2, c2] = CIDX[chh if a > 0.18 else "."]
                    fg[r2, c2] = col * min(1.0, 0.25 + a)


class Meteor:
    def __init__(self, rng, cols, rows):
        self.rng, self.cols, self.rows = rng, cols, rows
        self.respawn(initial=True)

    def respawn(self, initial=False):
        g = self.rng
        self.dir = g.choice([-1, 1])
        self.x = g.uniform(0.05, 0.95) * self.cols
        self.y = g.uniform(0.05, 0.55) * self.rows
        self.vx = self.dir * g.uniform(26, 40)
        self.vy = g.uniform(11, 17)
        self.life = g.uniform(0.35, 0.7)
        self.age = 0.0
        self.wait = g.uniform(0.5, 5.0) if not initial else g.uniform(2.0, 6.0)

    def step(self, dt):
        if self.wait > 0:
            self.wait -= dt
            return
        self.age += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.age > self.life:
            self.respawn()

    def stamp(self, idx, fg, pmc):
        if self.wait > 0:
            return
        ch = "\\" if self.dir > 0 else "/"
        fade = 1.0 - self.age / self.life
        n = 9
        for k in range(n):
            x = self.x - self.vx * 0.026 * k
            y = self.y - self.vy * 0.026 * k
            c, r = int(round(x)), int(round(y))
            if 0 <= r < self.rows and 0 <= c < self.cols and pmc[r, c] > 0.5:
                a = (1 - k / n) * fade
                if k == 0:
                    idx[r, c] = CIDX["@"]
                    fg[r, c] = (200, 225, 255)
                else:
                    idx[r, c] = CIDX[ch]
                    fg[r, c] = np.array((150, 190, 255)) * (0.25 + 0.75 * a)


_nrng = np.random.default_rng(3)
_NDIR = _nrng.normal(size=(24, 3))
_NDIR /= np.linalg.norm(_NDIR, axis=1)[:, None]
_NPH = _nrng.uniform(0, 2 * math.pi, 24)


def snoise3(n, freq, off=0, octaves=3, tph=0.0):
    """n: (N,3) unit vectors -> (N,) smooth noise, roughly 0..1.  tph makes it boil over time."""
    out = np.zeros(len(n), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        for j in range(4):
            i = (o * 4 + j + off) % 24
            out += amp * np.sin((n @ _NDIR[i]) * freq * (2.0 ** o) * (1 + 0.13 * j)
                                + _NPH[i] + tph * (0.5 + 0.25 * j))
            tot += amp
        amp *= 0.5
    return np.clip(0.5 + 0.5 * out / (tot * 0.62), 0, 1)


def spin(dx, dy, dz, a):
    """rotate the surface normal about the vertical axis (makes the body turn)"""
    c, s_ = math.cos(a), math.sin(a)
    return np.stack([dx * c + dz * s_, dy, -dx * s_ + dz * c], -1).astype(np.float32)


def _unit(rng, count):
    v = rng.normal(size=(count, 3))
    return (v / np.linalg.norm(v, axis=1)[:, None]).astype(np.float32)


_crng = np.random.default_rng(21)
_CR_C = _unit(_crng, 150)
_CR_R = (0.035 + 0.25 * _crng.random(150) ** 3).astype(np.float32)
_SP_C = _unit(_crng, 16)
_SP_R = _crng.uniform(0.07, 0.17, 16).astype(np.float32)
_RY_C = _unit(_crng, 4)
_RY_T1 = np.cross(_RY_C, _unit(_crng, 4))
_RY_T1 = (_RY_T1 / np.linalg.norm(_RY_T1, axis=1)[:, None]).astype(np.float32)
_RY_T2 = np.cross(_RY_C, _RY_T1).astype(np.float32)
_RY_K = np.array([9, 11, 13, 10], np.float32)
_RY_PH = _crng.uniform(0, 6.28, 4).astype(np.float32)


def crater_field(n):
    ang = np.arccos(np.clip(n @ _CR_C.T, -1, 1))
    u = ang / _CR_R
    floor = (u < 1) * (1 - u * u)
    rim = np.exp(-((u - 1.0) / 0.16) ** 2)
    peak = (u < 0.18) * (1 - u / 0.18) * (_CR_R > 0.12)
    return (0.9 * rim - 1.0 * floor + 0.8 * peak).sum(1)


def ray_field(n):
    """bright streaks thrown out from a few young craters (like Tycho)"""
    ang = np.arccos(np.clip(n @ _RY_C.T, -1, 1))
    az = np.arctan2(n @ _RY_T2.T, n @ _RY_T1.T)
    streak = (0.5 + 0.5 * np.cos(az * _RY_K + _RY_PH)) ** 7
    return np.clip((streak * np.exp(-ang / 0.65) * ss(0.05, 0.16, ang)).sum(1), 0, 1)


def spot_fields(n):
    ang = np.arccos(np.clip(n @ _SP_C.T, -1, 1))
    umbra = np.clip(1 - ang / (0.5 * _SP_R), 0, 1).sum(1).clip(0, 1)
    pen = np.clip(1 - ang / _SP_R, 0, 1).sum(1).clip(0, 1)
    return umbra, pen


def shade_sun(dx, dy, dz, t, light=None):
    """Boiling granulation, sunspots with a penumbra, bright active regions, strong limb darkening."""
    n = spin(dx, dy, dz, t * 0.04)
    gran = snoise3(n, 12.0, 0, 3, t * 0.25)
    cells = 1.0 - np.abs(2 * gran - 1)
    fine = snoise3(n, 34.0, 8, 1, t * 0.5)
    plage = snoise3(n, 3.0, 15, 2, t * 0.05)
    umbra, pen = spot_fields(n)
    limb = dz ** 0.5
    dens = (0.50 + 0.26 * limb + 0.16 * (cells - 0.5) + 0.06 * (fine - 0.5)
            + 0.10 * (plage - 0.5) - 0.36 * umbra - 0.14 * pen)
    c_edge = np.array([214, 70, 14], np.float32)
    c_mid = np.array([255, 205, 95], np.float32)
    c_core = np.array([255, 244, 208], np.float32)
    col = c_edge + (c_mid - c_edge) * (limb ** 1.5)[:, None]
    col = col + (c_core - col) * (0.8 * ss(0.75, 1.0, limb))[:, None]
    col = col * (0.72 + 0.28 * cells + 0.10 * (plage - 0.5))[:, None]
    col = col * (1 - 0.75 * umbra - 0.35 * pen)[:, None]
    return np.clip(dens, 0, 1), np.clip(col, 0, 255)


def shade_moon(dx, dy, dz, t, light):
    """Silvery moon: many craters with bright rims, ray systems, dark maria, a real terminator."""
    lx, ly, lz = light
    n = spin(dx, dy, dz, 0.5 + t * 0.015)
    cr = crater_field(n)
    rays = ray_field(n)
    maria = ss(0.52, 0.60, snoise3(n, 1.8, 5, 3))
    reg = snoise3(n, 14.0, 12, 2)
    lam = np.clip(dx * lx + dy * ly + dz * lz, 0, 1)
    albedo = np.clip(0.80 - 0.42 * maria + 0.26 * cr + 0.34 * rays + 0.16 * (reg - 0.5), 0.15, 1.25)
    light_k = 0.16 + 0.84 * lam ** 0.7
    dens = 0.30 + 0.62 * light_k * albedo + 0.10 * cr
    base = np.array([214, 226, 255], np.float32)
    shine = np.array([30, 52, 120], np.float32)
    col = base * (albedo * light_k)[:, None] * 1.6 + shine * ((1 - lam) * 0.45)[:, None]
    return np.clip(dens, 0, 1), np.clip(col, 0, 255)


EARTH_LIGHT = np.array([-0.5, -0.32, 0.8], np.float32)
EARTH_LIGHT /= np.linalg.norm(EARTH_LIGHT)


def shade_earth(dx, dy, dz, t, light=None):
    """Oceans, shallow seas, green and brown land, deserts, ice caps, moving clouds, city lights."""
    lx, ly, lz = EARTH_LIGHT
    n = spin(dx, dy, dz, t * 0.12)
    warp = np.stack([snoise3(n, 1.6, 3, 2), snoise3(n, 1.6, 7, 2), snoise3(n, 1.6, 11, 2)], -1) - 0.5
    f = snoise3(n + 0.9 * warp, 2.4, 2, 4)
    land = ss(0.51, 0.55, f)
    shallow = ss(0.42, 0.51, f) * (1 - land)
    elev = snoise3(n, 6.5, 9, 3)
    lat = np.abs(n[:, 1])
    desert = ss(0.16, 0.32, lat) * (1 - ss(0.44, 0.60, lat)) * ss(0.45, 0.60, snoise3(n, 3.2, 17, 2))
    ice = np.clip(ss(0.80, 0.90, lat) + 0.7 * ss(0.68, 0.80, elev) * land * ss(0.60, 0.78, lat), 0, 1)

    deep = np.array([16, 78, 205], np.float32)
    shal = np.array([46, 178, 214], np.float32)
    green = np.array([62, 170, 74], np.float32)
    brown = np.array([176, 138, 80], np.float32)
    sand = np.array([210, 178, 108], np.float32)
    ocean = deep + (shal - deep) * shallow[:, None]
    land_c = green + (brown - green) * np.clip((elev - 0.42) * 2.6, 0, 1)[:, None]
    land_c = land_c * (1 - desert)[:, None] + sand * desert[:, None]
    col = ocean * (1 - land)[:, None] + land_c * land[:, None]
    col = col * (1 - ice)[:, None] + 240 * ice[:, None]

    ncl = spin(dx, dy, dz, t * 0.17)
    cloud = ss(0.56, 0.74, snoise3(ncl, 3.6, 14, 4, t * 0.02)) * 0.90
    col = col * (1 - cloud)[:, None] + np.array([244, 247, 255], np.float32) * cloud[:, None]

    lam = np.clip(0.58 + 0.42 * (dx * lx + dy * ly + dz * lz), 0, 1)
    atm = (1 - dz) ** 2.5
    col = (col * lam[:, None] + atm[:, None] * np.array([110, 175, 255], np.float32) * 0.8) * 1.12
    night = 1 - ss(0.28, 0.50, lam)
    cities = night * land * ss(0.68, 0.80, snoise3(n, 28.0, 20, 1)) * (1 - cloud)
    col = col + cities[:, None] * np.array([255, 190, 90], np.float32) * 0.9

    dens = 0.44 + 0.16 * land + 0.34 * cloud + 0.26 * ice + 0.12 * (lam - 0.5) + 0.20 * cities
    dens = dens * (0.82 + 0.18 * dz ** 0.5)
    return np.clip(dens, 0, 1), np.clip(col, 0, 255)


_prng = np.random.default_rng(8)
_PR_A = _prng.uniform(0, 2 * math.pi, 6)
_PR_H = _prng.uniform(0.04, 0.10, 6)
_PR_W = _prng.uniform(0.10, 0.22, 6)
_PR_PH = _prng.uniform(0, 6.28, 6)
_PR_DR = _prng.uniform(-0.03, 0.03, 6)


def closeness(t):
    """0 = sun and moon far apart, 1 = fused into one planet. Slow, and it loops."""
    u = (t % CYCLE) / CYCLE
    if u < 0.08:
        return 0.0
    if u < 0.54:
        return (u - 0.08) / 0.46
    if u < 0.76:
        return 1.0
    if u < 0.94:
        return 1.0 - (u - 0.76) / 0.18
    return 0.0


def smin(a, b, k):
    """polynomial smooth-min: two shapes bulge toward each other and fuse like liquid"""
    if k <= 1e-6:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


class Scene:
    def __init__(self, cols, rows, CW, CHh):
        self.cols, self.rows, self.CW, self.CHh = cols, rows, CW, CHh
        self.W, self.H = cols * CW, rows * CHh
        self.aspect = CHh / CW
        rr, cc = np.mgrid[0:rows, 0:cols]
        self.X = cc + 0.5
        self.Y = (rr + 0.5) * self.aspect
        self.cx = cols / 2.0
        self.cy = rows * self.aspect / 2.0
        self.unit_h = rows * self.aspect
        self.stars = Stars(self.W, self.H)
        rng = np.random.default_rng(5)
        self.meteors = [Meteor(rng, cols, rows) for _ in range(N_METEORS)]
        gen = np.random.default_rng(9)
        r1 = gen.random((rows, cols)).astype(np.float32)
        r2 = gen.random((rows, cols)).astype(np.float32)
        r3 = gen.random((rows, cols)).astype(np.float32)
        self.reveal = r1


        dist = np.hypot(self.X - self.cx, self.Y - self.cy)
        far = np.clip(dist / (0.55 * 2 * ORBIT_R * cols + SUN_RAD * self.unit_h), 0, 1).astype(np.float32)
        self.rev_s = 0.65 * r1 + 0.35 * (1 - far)
        self.rev_m = 0.65 * r2 + 0.35 * (1 - far)
        self.rev_e = 0.60 * r3 + 0.40 * far
        self.t_prev = 0.0


    def geometry(self, t):
        uh = self.unit_h
        c = closeness(t)
        rs0, rm0, rc = SUN_RAD * uh, MOON_RAD * uh, EARTH_RAD * uh
        D0 = 2 * ORBIT_R * self.cols
        p = min(1.0, c / 0.85)
        p = 0.65 * p ** 1.6 + 0.35 * sstep(p)
        D = D0 * (1 - p)
        m = sstep((c - 0.10) / 0.75)
        rs = rs0 + (rc - rs0) * m
        rm = rm0 + (rc - rm0) * m

        phi = (0.20 * math.sin(t * 2 * math.pi / 31.0) + 0.07 * math.sin(t * 2 * math.pi / 13.0 + 1.0)
               + 2.3 * math.pi * p ** 1.15)
        ux, uy = math.cos(phi), math.sin(phi)
        sx, sy = self.cx - 0.45 * D * ux, self.cy - 0.45 * D * uy
        mx, my = self.cx + 0.55 * D * ux, self.cy + 0.55 * D * uy

        k = 9.0 * ss(0.30, 0.55, c) * (1 - sstep((c - 0.62) / 0.20))
        swirl = 3.4 * ss(0.22, 0.52, c) * (1 - ss(0.66, 0.96, c))
        return c, sx, sy, mx, my, rs, rm, k, swirl

    @staticmethod
    def shade_at(fn, dx, dy, r2, m, t, light):
        """shade only the covered pixels; pixels past the rim are clamped onto the limb"""
        r = np.sqrt(r2[m])
        sc = np.maximum(1.0, r)
        nx, ny = dx[m] / sc, dy[m] / sc
        nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0.03, 1))
        return fn(nx, ny, nz, t, light)


    def frame(self, t):
        dt = max(0.0, min(0.1, t - self.t_prev))
        self.t_prev = t
        rows, cols = self.rows, self.cols

        c, sx, sy, mx, my, rs, rm, k, swirl = self.geometry(t)


        ddx, ddy = self.X - self.cx, self.Y - self.cy
        rr0 = np.hypot(ddx, ddy)
        a_ = swirl * np.exp(-(rr0 / (0.27 * self.unit_h)) ** 2)
        ca, sa = np.cos(a_), np.sin(a_)
        X = self.cx + ddx * ca - ddy * sa
        Y = self.cy + ddx * sa + ddy * ca
        rE = 0.5 * (rs + rm) * (0.55 + 0.45 * sstep((c - 0.28) / 0.60))
        e = float(ss(0.30, 0.82, c))
        pres_s = 1.0 - float(ss(0.34, 0.86, c))
        pres_m = 1.0 - float(ss(0.38, 0.88, c))
        shown_s = self.rev_s <= pres_s * 1.0001 + 1e-6
        shown_m = self.rev_m <= pres_m * 1.0001 + 1e-6

        dxs, dys = (X - sx) / rs, (Y - sy) / rs
        dxm, dym = (X - mx) / rm, (Y - my) / rm
        r2s, r2m = dxs * dxs + dys * dys + 1e-9, dxm * dxm + dym * dym + 1e-9
        d_s = (np.sqrt(r2s) - 1.0) * rs
        d_m = (np.sqrt(r2m) - 1.0) * rm
        inside = smin(d_s, d_m, k) <= 0.0
        wsp = 1.0 / (1.0 + np.exp(np.clip((d_s - d_m) / 6.0, -30, 30)))
        wmp = 1.0 - wsp


        vx, vy = sx - mx, sy - my
        vn = math.hypot(vx, vy)
        ux, uy = (vx / vn, vy / vn) if vn > 1e-3 else (-1.0, 0.0)
        wf = float(ss(0.25, 0.70, c))
        lv = np.array([(1 - wf) * 0.85 * ux + wf * -0.5,
                       (1 - wf) * 0.85 * uy + wf * -0.32,
                       0.5 * (1 - wf) + 0.8 * wf], np.float64)
        lv /= np.linalg.norm(lv)

        Ds = np.zeros((rows, cols), np.float32)
        Dm = np.zeros((rows, cols), np.float32)
        Cs = np.zeros((rows, cols, 3), np.float32)
        Cm = np.zeros((rows, cols, 3), np.float32)
        ms = inside & shown_s
        mm = inside & shown_m
        if ms.any():
            Ds[ms], Cs[ms] = self.shade_at(shade_sun, dxs, dys, r2s, ms, t, None)
        if mm.any():
            Dm[mm], Cm[mm] = self.shade_at(shade_moon, dxm, dym, r2m, mm, t, lv)

        both = shown_s & shown_m
        ws2 = np.where(both, wsp, np.where(shown_s, 1.0, 0.0)).astype(np.float32)
        wm2 = np.where(both, wmp, np.where(shown_m, 1.0, 0.0)).astype(np.float32)
        L = Ds * ws2 + Dm * wm2
        fg = Cs * ws2[..., None] + Cm * wm2[..., None]


        dxe, dye = (X - self.cx) / rE, (Y - self.cy) / rE
        r2e = dxe * dxe + dye * dye + 1e-9
        if e > 0.01:
            shown_e = self.rev_e <= e * 1.0001 + 1e-6
            me = inside & shown_e & (r2e <= 1.5)
            if me.any():
                De, Ce = self.shade_at(shade_earth, dxe, dye, r2e, me, t, None)
                wE = np.zeros((rows, cols), np.float32)
                wE[me] = (1 - ss(1.00, 1.10, np.sqrt(r2e[me]))).astype(np.float32)
                DeF = np.zeros((rows, cols), np.float32)
                CeF = np.zeros((rows, cols, 3), np.float32)
                DeF[me], CeF[me] = De, Ce
                L = L * (1 - wE) + DeF * wE
                fg = fg * (1 - wE)[..., None] + CeF * wE[..., None]


        sun_alive = pres_s
        if sun_alive > 0.01:
            rr = np.sqrt(r2s)
            ring = (~inside) & (rr < 1.24) & (wsp > 0.5)
            if ring.any():
                ang = np.arctan2(Y - sy, X - sx)[ring]
                rg = rr[ring]
                rays = 0.55 + 0.45 * np.sin(ang * 7 + t * 0.3) * np.sin(ang * 3 - t * 0.2)
                fall = np.clip(1 - (rg - 1.0) / 0.22, 0, 1) ** 1.9
                Lc = 0.11 * fall * rays
                Lp = np.zeros_like(Lc)
                for p in range(6):
                    a0 = _PR_A[p] + _PR_DR[p] * t
                    da = (ang - a0 + math.pi) % (2 * math.pi) - math.pi
                    h = _PR_H[p] * (0.65 + 0.35 * math.sin(t * 0.4 + _PR_PH[p])) * np.exp(-(da / _PR_W[p]) ** 2)
                    arch = (rg > 1.0) & ((rg - 1.0) < h)
                    Lp = np.maximum(Lp, arch * (0.28 + 0.32 * (1 - (rg - 1.0) / (h + 1e-6))))
                use_p = Lp > Lc
                Lr = np.maximum(Lc, Lp) * sun_alive
                colr = np.where(use_p[:, None], np.array([255, 96, 36], np.float32),
                                np.array([232, 122, 42], np.float32))
                colr = colr * (0.35 + 0.65 * np.clip(Lr / 0.4, 0, 1))[:, None]
                L[ring] = np.maximum(L[ring], Lr)
                fg[ring] = np.where((Lr > 0.02)[:, None], colr, fg[ring])


        if e > 0.3:
            ring2 = (~inside) & (r2e > 1.0) & (r2e < 1.26)
            if ring2.any():
                fall2 = np.clip(1 - (np.sqrt(r2e[ring2]) - 1.0) / 0.12, 0, 1) ** 1.5
                L[ring2] = np.maximum(L[ring2], 0.10 * fall2 * e)
                fg[ring2] = np.array([100, 170, 255], np.float32) * (0.4 + 0.6 * fall2)[:, None]


        gray = fg.mean(-1, keepdims=True)
        fg = np.clip((gray + (fg - gray) * VIBRANCE) * 1.04, 0, 255).astype(np.float32)


        prog_s = float(ss(0.0, 1.0, t / PLANET_FADE_IN))
        prog_m = float(ss(0.0, 1.0, (t - 0.8) / PLANET_FADE_IN))
        prog = np.where(wsp > 0.5, prog_s, prog_m).astype(np.float32)
        shown = self.reveal < prog * 1.05
        L = np.where(shown, L, 0.0).astype(np.float32)
        fg = fg * (shown * (0.2 + 0.8 * prog))[..., None]


        i = (np.clip(L, 0, 1) * (len(RAMP) - 1)).astype(np.int32)
        idx = RAMP_IDX[i]
        idx[L < 0.03] = SPACE


        pmc = (L < 0.06).astype(np.float32)

        amt = float(ss(0.0, 1.0, t / STAR_FADE_IN))
        amt *= 0.85 + 0.15 * math.sin(t * 0.35)
        stamp_stars(self.stars, self.CW, self.CHh, idx, fg, L, t, amt, pmc, self.stars.scol)

        for mt in self.meteors:
            mt.step(dt)
            mt.stamp(idx, fg, pmc)
        return idx, fg


GLOW_GAIN = 1.7


def build_atlas(glyph_alpha_fn, n_chars, CW, CHh):
    atlas = np.zeros((n_chars, CHh, CW), np.float32)
    for i, c in enumerate(CHARS):
        a = glyph_alpha_fn(c)
        h, w = min(CHh, a.shape[0]), min(CW, a.shape[1])
        atlas[i, :h, :w] = a[:h, :w]
    return atlas


def render(atlas, cover, idx, fg, CW, CHh):
    """
    Returns (sharp, glow):
      sharp - full-size uint8 image of the characters
      glow  - tiny uint8 image (one pixel per cell, blurred); the caller scales it up and adds it
    """
    rows, cols = idx.shape
    g = atlas[idx]
    sharp = np.einsum("rcyx,rck->rycxk", g, fg).reshape(rows * CHh, cols * CW, 3)
    sharp = np.clip(sharp, 0, 255).astype(np.uint8)

    glow = fg * cover[idx][..., None]
    for _ in range(2):
        glow = (glow * 2 + np.roll(glow, 1, 0) + np.roll(glow, -1, 0) +
                np.roll(glow, 1, 1) + np.roll(glow, -1, 1)) / 6
    glow = np.clip(glow * GLOW_GAIN, 0, 255).astype(np.uint8)
    return sharp, glow


def main():
    import pygame
    pygame.init()
    font = pygame.font.SysFont("menlo,consolas,dejavusansmono,couriernew,monospace", FONT_SIZE, bold=True)
    CW, CHh = font.size("M")[0], font.get_linesize()

    def glyph_alpha(c):
        s = font.render(c, True, (255, 255, 255))
        return pygame.surfarray.array_alpha(s).T.astype(np.float32) / 255.0

    atlas = build_atlas(glyph_alpha, len(CHARS), CW, CHh)
    cover = atlas.mean((1, 2))
    W, H = COLS * CW, ROWS * CHh
    try:
        dw, dh = pygame.display.get_desktop_sizes()[0]
    except Exception:
        info = pygame.display.Info()
        dw, dh = info.current_w, info.current_h
    fit = min(1.0, dw * 0.72 / W, dh * 0.58 / H)
    pygame.display.set_mode((max(1, int(W * fit)), max(1, int(H * fit))), pygame.RESIZABLE)
    canvas = pygame.Surface((W, H))
    pygame.display.set_caption("Sun & Moon")
    clock = pygame.time.Clock()
    scene = Scene(COLS, ROWS, CW, CHh)

    music_ok = False
    song = os.path.join(os.path.dirname(os.path.abspath(__file__)), AUDIO_FILE)
    if os.path.exists(song):
        try:
            pygame.mixer.init()
            pygame.mixer.music.load(song)
            music_ok = True
        except Exception:
            music_ok = False
    cycle_no = -1

    t, running = 0.0, True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                running = False
        if music_ok:
            n = int(t / CYCLE)
            tc = t - n * CYCLE
            if n != cycle_no:
                cycle_no = n
                pygame.mixer.music.set_volume(0.0)
                pygame.mixer.music.play()
            pygame.mixer.music.set_volume(AUDIO_VOLUME * max(0.0, min(1.0, tc / AUDIO_FADE, (CYCLE - tc) / AUDIO_FADE)))
        idx, fg = scene.frame(t)
        sharp, glow = render(atlas, cover, idx, fg, CW, CHh)
        canvas.blit(pygame.surfarray.make_surface(sharp.swapaxes(0, 1)), (0, 0))
        halo = pygame.transform.smoothscale(pygame.surfarray.make_surface(glow.swapaxes(0, 1)), (W, H))
        canvas.blit(halo, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        window = pygame.display.get_surface()
        ww, wh = window.get_size()
        s = min(ww / W, wh / H)
        size = (max(1, int(W * s)), max(1, int(H * s)))
        window.fill((0, 0, 0))
        window.blit(pygame.transform.smoothscale(canvas, size), (int((ww - size[0]) / 2), int((wh - size[1]) / 2)))
        pygame.display.flip()
        t += 1.0 / FPS
        clock.tick(FPS)
    pygame.quit()


if __name__ == "__main__":
    main()
