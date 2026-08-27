#!/usr/bin/env python3
"""
Gera os SVGs animados de assets/ a partir do avatar do GitHub.

    pip install -r tools/requirements.txt
    python3 tools/gen_assets.py

Saída: assets/header.svg, assets/portrait.svg, assets/stack.svg
"""
import os
import sys
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import svgkit
from svgkit import C, chrome, cursor, fade_in, hidden, svg, text, typed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
CACHE = os.path.join(ROOT, ".cache")
AVATAR_URL = "https://avatars.githubusercontent.com/u/200270758?v=4&s=460"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

W = 880
LS = ' letter-spacing="2.4"'


# --------------------------------------------------------------------------
# avatar → recorte do sujeito
# --------------------------------------------------------------------------
def avatar_path():
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, "avatar.jpg")
    if not os.path.exists(p):
        urllib.request.urlretrieve(AVATAR_URL, p)
    return p


def subject_mask(path):
    """Separa a pessoa do fundo com GrabCut. As sementes abaixo são
    específicas deste avatar (460x460); troque-as se a foto mudar."""
    import cv2
    from scipy import ndimage

    img = cv2.imread(path)
    h, w = img.shape[:2]
    m = np.full((h, w), cv2.GC_BGD, np.uint8)
    m[130:460, 115:345] = cv2.GC_PR_BGD      # área provável do sujeito
    m[145:225, 190:270] = cv2.GC_PR_FGD      # cabeça
    m[175:200, 200:255] = cv2.GC_FGD         # cabelo
    m[205:210, 215:245] = cv2.GC_FGD         # rosto
    m[240:370, 175:290] = cv2.GC_FGD         # camiseta
    m[390:455, 205:275] = cv2.GC_FGD         # calça
    m[175:235, 285:345] = cv2.GC_BGD         # cartaz na parede
    m[100:150, :] = cv2.GC_BGD
    cv2.grabCut(img, m, None, np.zeros((1, 65), np.float64),
                np.zeros((1, 65), np.float64), 10, cv2.GC_INIT_WITH_MASK)
    fg = np.isin(m, [cv2.GC_FGD, cv2.GC_PR_FGD])
    fg = ndimage.binary_fill_holes(ndimage.binary_closing(fg, np.ones((7, 7))))
    lab, n = ndimage.label(fg)
    sizes = ndimage.sum(fg, lab, range(1, n + 1))
    return lab == (np.argmax(sizes) + 1)     # maior componente = a pessoa


def ascii_portrait(path, mask, cols=56, ramp=" .:-=+*#%@",
                   contrast=1.8, floor=0.45, pad=3):
    """Converte o recorte em arte ASCII: brilho do pixel vira densidade do caractere."""
    ys, xs = np.where(mask)
    box = (max(xs.min() - pad, 0), max(ys.min() - pad, 0),
           min(xs.max() + pad, mask.shape[1]), min(ys.max() + pad, mask.shape[0]))
    g = Image.open(path).convert("L").crop(box)
    g = g.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=2))
    a = np.asarray(g).astype(float)
    mm = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).crop(box)) > 127
    lo, hi = np.percentile(a[mm], 2), np.percentile(a[mm], 98)
    a = np.clip((a - lo) / max(hi - lo, 1e-6), 0, 1)
    a = np.clip((a - 0.5) * contrast + 0.5, 0, 1)
    a[~mm] = 0.0

    h, w = a.shape
    rows = max(1, round(cols * (h / w) * 0.50))   # célula de texto ≈ 0.5 de largura/altura
    small = np.asarray(Image.fromarray((a * 255).astype(np.uint8))
                       .resize((cols, rows), Image.LANCZOS)) / 255.0
    cover = np.asarray(Image.fromarray((mm * 255).astype(np.uint8))
                       .resize((cols, rows), Image.LANCZOS)) / 255.0
    out = []
    for y in range(rows):
        line = []
        for x in range(cols):
            c = cover[y, x]
            if c < 0.30:
                line.append(" ")
                continue
            v = np.clip(small[y, x] / max(c, 1e-6), 0, 1)
            v = (floor + (1 - floor) * v) * min(1.0, 0.55 + 0.45 * c / 0.85)
            line.append(ramp[min(len(ramp) - 1, max(1, int(v * (len(ramp) - 1) + 0.5)))])
        out.append("".join(line).rstrip())
    ind = min((len(l) - len(l.lstrip()) for l in out if l.strip()), default=0)
    return [l[ind:] for l in out]


# --------------------------------------------------------------------------
# header: nome em blocos 3D
# --------------------------------------------------------------------------
def word_bitmap(word, cols, track=2):
    """Rasteriza a palavra numa grade booleana de `cols` colunas."""
    fs = 200
    f = ImageFont.truetype(FONT_BOLD, fs)
    widths = [f.getlength(c) for c in word]
    gap = track * fs * 0.02
    img = Image.new("L", (int(sum(widths) + gap * (len(word) - 1)) + 20, int(fs * 1.6)), 0)
    d = ImageDraw.Draw(img)
    x = 10
    for c, wd in zip(word, widths):
        d.text((x, 10), c, font=f, fill=255)
        x += wd + gap
    img = img.crop(img.getbbox())
    w, h = img.size
    return np.asarray(img.resize((cols, max(1, round(cols * (h / w) * 0.50))),
                                 Image.LANCZOS)) > 110


def slab_3d(word, cell, depth, x0, y0, gid="slb"):
    """Blocos 3D em <rect> — idêntico em qualquer fonte, ao contrário de texto."""
    b = word_bitmap(word, cols=int((W - 70 - depth) / cell))
    rows, cols = b.shape
    cells = []
    for y in range(rows):
        x = 0
        while x < cols:
            if b[y, x]:
                x2 = x
                while x2 + 1 < cols and b[y, x2 + 1]:   # junta vizinhos numa <rect> só
                    x2 += 1
                cells.append(f'<rect x="{x*cell}" y="{y*cell}" '
                             f'width="{(x2-x+1)*cell}" height="{cell}"/>')
                x = x2 + 1
            else:
                x += 1
    out = [f'<defs><g id="{gid}">{"".join(cells)}</g></defs>',
           f'<g transform="translate({x0},{y0})">']
    for d in range(depth, 0, -1):                       # extrusão, do fundo para a frente
        f = 0.30 + 0.34 * (depth - d) / max(depth - 1, 1)
        out.append(f'<use href="#{gid}" transform="translate({d},{-d})" '
                   f'fill="#{int(0x6e*f+20):02x}{int(0x3f*f+16):02x}{int(0xc4*f+30):02x}"/>')
    out.append(f'<use href="#{gid}" fill="{C["pur2"]}"/></g>')
    return "".join(out), cols * cell + depth, rows * cell + depth


def build_header():
    FS = 13.0
    CH = FS * 0.60
    cell, depth = 8, 7
    art, aw, ah = slab_3d("TEUSLUV", cell, depth, 30, 78)
    p, y = [], 56
    g, t = typed("teusluv@github:~$ ./banner.sh --render TEUSLUV --3d",
                 28, y, FS, C["fg"], CH, "c1", 0.3)
    p.append(g)
    if svgkit.PREVIEW:
        p.append(art)
    else:                                               # o nome é "impresso" da esquerda p/ direita
        p.append(f'<clipPath id="wipe"><rect x="28" y="70" width="0" height="{ah+16}">'
                 f'<animate attributeName="width" from="0" to="{aw+14}" '
                 f'begin="{t+0.15:.2f}s" dur="1.15s" fill="freeze"/></rect></clipPath>'
                 f'<g clip-path="url(#wipe)">{art}</g>')
        t += 1.3
    y = 78 + ah + 30
    x = 28
    for fill, s in ((C["dim"], "// "), (C["wht"], "José Mateus Santos Nunes"),
                    (C["dim"], "  —  desenvolvedor full stack")):
        p.append(f'<g{hidden()}>{fade_in(t + 0.1, 0.3)}{text(s, x, y, FS, fill, CH)}</g>')
        x += CH * len(s)
    y += 25
    g, t2 = typed("Java · Spring Boot · React · Next.js · Docker · PostgreSQL",
                  28, y, FS, C["cya"], CH, "c2", t + 0.45)
    p.append(g)
    y += 27
    g, t3 = typed("teusluv@github:~$ ", 28, y, FS, C["grn"], CH, "c3", t2 + 0.25)
    p.append(g)
    p.append(cursor(28 + CH * 18, y, FS, CH, t3 + 0.05))
    H = int(y + 24)
    return svg(W, H, chrome(W, H, "teusluv@github: ~") + "".join(p),
               "TEUSLUV — José Mateus Santos Nunes, desenvolvedor full stack")


# --------------------------------------------------------------------------
# retrato + painel
# --------------------------------------------------------------------------
TIERS = [(" .:-", "#7b5cb8"), ("=+*", "#ab7cf9"), ("#%@", "#e0caff")]
BIO = ["Estudante de tecnologia que aprende construindo:",
       "APIs em Java/Spring no backend e interfaces em",
       "React/Next.js no frontend — do banco ao browser."]
ROWS = [("foco", "Spring Boot · Docker · microsserviços"),
        ("stack", "Java · React · PostgreSQL · Linux"),
        ("local", "Brasil"),
        ("idiomas", "Português nativo · Inglês intermediário"),
        ("status", "aberto a estágio e vagas júnior")]
CHIPS = [("APIs REST", C["blu"]), ("Open Source", C["grn"]),
         ("UI/UX", C["pur2"]), ("Cibersegurança", C["yel"])]
DESTAQUES = ["APIs REST com Java + Spring Boot",
             "Interfaces com React e Next.js",
             "Projetos ponta a ponta: back, front e banco"]


def section(label, x, y):
    return (f'<g{hidden()}>{{anim}}{text(label, x, y, 10.5, C["dim"], extra=LS)}'
            f'<rect x="{x}" y="{y+7}" width="26" height="2" rx="1" fill="{C["pur"]}"/></g>')


def build_portrait(art):
    FSA, FS = 11.4, 12.6
    CHA, CH = FSA * 0.60, FS * 0.60
    ax = 30 + (420 - CHA * max(len(l) for l in art)) / 2
    lh = FSA * 1.06
    p, y = [], 56
    g, t = typed("teusluv@github:~$ ./retrato.sh --avatar --ascii",
                 28, y, FS, C["fg"], CH, "p1", 0.3)
    p.append(g)
    ya = y + 22
    for i, line in enumerate(art):
        if not line.strip():
            continue
        layers = []
        for chars, col in TIERS:              # densidade vira brilho: dá volume ao retrato
            keep = "".join(c if c in chars else " " for c in line)
            if keep.strip():
                layers.append(text(keep, ax, ya + i * lh, FSA, col, CHA))
        p.append(f'<g{hidden()}>{fade_in(t + 0.2 + i * 0.045, 0.3)}{"".join(layers)}</g>')
    tp = t + 0.2 + len(art) * 0.045

    x, py = 470, ya + 14
    p.append(section("SOBRE", x, py).format(anim=fade_in(t + 0.35)))
    py += 30
    for i, line in enumerate(BIO):
        p.append(f'<g{hidden()}>{fade_in(t + 0.5 + i * 0.18)}{text(line, x, py, FS, C["fg"], CH)}</g>')
        py += 19
    py += 16
    kw = max(len(k) for k, _ in ROWS) + 2
    for i, (k, v) in enumerate(ROWS):
        p.append(f'<g{hidden()}>{fade_in(t + 1.15 + i * 0.16)}'
                 f'{text(k.ljust(kw), x, py, FS, C["pur"], CH)}'
                 f'{text(v, x + CH * kw, py, FS, C["fg"], CH)}</g>')
        py += 21
    py += 20
    cx = x
    for i, (label, col) in enumerate(CHIPS):
        w = CH * len(label) + 20
        if cx + w > W - 26:
            cx, py = x, py + 28
        p.append(f'<g{hidden()}>{fade_in(t + 2.0 + i * 0.14)}'
                 f'<rect x="{cx}" y="{py-12}" width="{w:.1f}" height="21" rx="10.5" '
                 f'fill="{col}" fill-opacity="0.13" stroke="{col}" stroke-opacity="0.45"/>'
                 f'{text(label, cx + 10, py + 3, 11.2, col, 11.2 * 0.60)}</g>')
        cx += w + 8
    py += 42
    p.append(section("DESTAQUES", x, py).format(anim=fade_in(t + 2.5)))
    py += 28
    for i, d in enumerate(DESTAQUES):
        p.append(f'<g{hidden()}>{fade_in(t + 2.7 + i * 0.18)}'
                 f'{text("▸", x, py, FS, C["grn"], CH)}'
                 f'{text(d, x + CH * 2, py, FS, C["fg"], CH)}</g>')
        py += 21
    py += 10

    yb = max(ya + len(art) * lh, py) + 16
    g, t2 = typed("teusluv@github:~$ ", 28, yb, FS, C["grn"], CH, "p2", tp + 0.3)
    p.append(g)
    p.append(cursor(28 + CH * 18, yb, FS, CH, t2 + 0.05))
    H = int(yb + 24)
    return svg(W, H, chrome(W, H, "teusluv@github: ~/perfil") + "".join(p),
               "retrato do avatar em ASCII ao lado de um resumo do perfil")


# --------------------------------------------------------------------------
# stack
# --------------------------------------------------------------------------
SKILLS = [
    [("Java", 0.90, "principal", C["yel"]),
     ("Spring Boot", 0.82, "backend", C["grn"]),
     ("MySQL", 0.72, "dados", C["blu"]),
     ("PostgreSQL", 0.62, "dados", C["blu"]),
     ("Git & Linux", 0.75, "diário", C["fg"])],
    [("React", 0.74, "frontend", C["cya"]),
     ("Next.js", 0.66, "frontend", C["cya"]),
     ("JavaScript", 0.70, "frontend", C["yel"]),
     ("HTML & CSS", 0.85, "base", C["red"]),
     ("Docker", 0.50, "estudando", C["pur2"])],
]


def build_stack():
    FS = 12.6
    CH = FS * 0.60
    BAR, LBL = 168, 13
    p = []
    g, t = typed("teusluv@github:~$ ./stack.sh --grafico", 28, 56, FS, C["fg"], CH, "s1", 0.3)
    p.append(g)
    y0 = 92
    for ci, col in enumerate(SKILLS):
        x = 30 + ci * 430
        for ri, (name, frac, tag, color) in enumerate(col):
            y = y0 + ri * 34
            b = t + 0.25 + (ri * 2 + ci) * 0.12
            bx = x + CH * LBL + 6
            wv = BAR * frac
            p.append(text(name.ljust(LBL), x, y + 4, FS, C["fg"], CH))
            p.append(f'<rect x="{bx}" y="{y-6}" width="{BAR}" height="9" rx="4.5" fill="{C["trk"]}"/>')
            anim = "" if svgkit.PREVIEW else (
                f'<animate attributeName="width" from="0" to="{wv:.1f}" begin="{b:.2f}s" '
                f'dur="0.85s" fill="freeze" calcMode="spline" '
                f'keySplines="0.22 1 0.36 1" keyTimes="0;1"/>')
            w0 = f"{wv:.1f}" if svgkit.PREVIEW else "0"
            p.append(f'<rect x="{bx}" y="{y-6}" width="{w0}" height="9" rx="4.5" '
                     f'fill="{color}">{anim}</rect>')
            p.append(f'<g{hidden()}>{fade_in(b + 0.55)}'
                     f'{text(tag, bx + BAR + 12, y + 4, 11.2, C["dim"], 11.2 * 0.60)}</g>')
    y = y0 + 5 * 34 + 16
    p.append(f'<line x1="30" y1="{y}" x2="{W-30}" y2="{y}" stroke="{C["edge"]}"/>')
    y += 28
    g, t2 = typed("// backend é onde eu moro; frontend é onde eu mostro o resultado.",
                  30, y, FS, C["dim"], CH, "s2", t + 1.9)
    p.append(g)
    y += 30
    g, t3 = typed("teusluv@github:~$ ", 28, y, FS, C["grn"], CH, "s3", t2 + 0.25)
    p.append(g)
    p.append(cursor(28 + CH * 18, y, FS, CH, t3 + 0.05))
    H = int(y + 24)
    return svg(W, H, chrome(W, H, "teusluv@github: ~/stack") + "".join(p),
               "grafico das tecnologias que eu uso")


def main():
    os.makedirs(ASSETS, exist_ok=True)
    path = avatar_path()
    art = ascii_portrait(path, subject_mask(path))
    for name, body in (("header.svg", build_header()),
                       ("portrait.svg", build_portrait(art)),
                       ("stack.svg", build_stack())):
        dest = os.path.join(ASSETS, name)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(body)
        print(f"gerado: assets/{name} ({len(body)} bytes)")


if __name__ == "__main__":
    main()
