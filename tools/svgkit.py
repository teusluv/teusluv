"""Blocos reutilizáveis para gerar 'cartões de terminal' em SVG animado."""
from xml.sax.saxutils import escape

PREVIEW = False   # True: gera versão estática, só para conferência local
MONO = ("ui-monospace,'SF Mono',SFMono-Regular,Menlo,Consolas,"
        "'Liberation Mono','DejaVu Sans Mono',monospace")
C = dict(bg="#0d1117", bar="#161b22", edge="#30363d", fg="#c9d1d9", dim="#6e7681",
         grn="#3fb950", blu="#58a6ff", pur="#a371f7", pur2="#bc8cff", yel="#d29922",
         red="#f85149", cya="#39d0d8", wht="#f0f6fc", trk="#21262d")

def mono():
    return "'DejaVu Sans Mono',monospace" if PREVIEW else MONO

def esc(s):
    return escape(s)

def text(s, x, y, size, fill, ch=None, weight=None, opacity=None, extra=""):
    """<text> com largura travada — mantém o alinhamento das colunas em qualquer fonte."""
    tl = f' textLength="{ch*len(s):.2f}" lengthAdjust="spacingAndGlyphs"' if (ch and s) else ""
    w = f' font-weight="{weight}"' if weight else ""
    o = f' opacity="{opacity}"' if opacity is not None else ""
    return (f'<text xml:space="preserve" x="{x:.2f}" y="{y:.2f}" font-family="{mono()}" '
            f'font-size="{size}" fill="{fill}"{w}{o}{tl}{extra}>{esc(s)}</text>')

def fade_in(begin, dur=0.28):
    if PREVIEW:
        return ""
    return (f'<animate attributeName="opacity" from="0" to="1" '
            f'begin="{begin:.2f}s" dur="{dur}s" fill="freeze"/>')

def hidden():
    return "" if PREVIEW else ' opacity="0"'

def chrome(w, h, title, radius=10):
    """Moldura da janela: barra de título, semáforo e borda."""
    p = [f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="{radius}" fill="{C["bg"]}" stroke="{C["edge"]}"/>',
         f'<path d="M0.5 {radius+0.5} a{radius} {radius} 0 0 1 {radius} -{radius} h{w-1-2*radius} '
         f'a{radius} {radius} 0 0 1 {radius} {radius} v27 h-{w-1} Z" fill="{C["bar"]}"/>',
         f'<line x1="0.5" y1="{radius+16.5}" x2="{w-0.5}" y2="{radius+16.5}" stroke="{C["edge"]}"/>']
    for i, col in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        p.append(f'<circle cx="{18+i*17}" cy="14" r="5.5" fill="{col}"/>')
    p.append(text(title, w/2, 18, 11.5, C["dim"], extra=' text-anchor="middle"'))
    return "".join(p)

def typed(s, x, y, size, fill, ch, cid, begin, cps=34, weight=None):
    """Linha revelada caractere a caractere, como se estivesse sendo digitada."""
    dur = max(0.25, len(s) / cps)
    if PREVIEW:
        return text(s, x, y, size, fill, ch, weight), begin + dur
    steps = ";".join(f"{ch*i:.2f}" for i in range(len(s) + 1))
    clip = (f'<clipPath id="{cid}"><rect x="{x-1:.2f}" y="{y-size:.2f}" width="0" height="{size*1.7:.2f}">'
            f'<animate attributeName="width" values="{steps}" begin="{begin:.2f}s" '
            f'dur="{dur:.2f}s" fill="freeze" calcMode="discrete"/></rect></clipPath>')
    return clip + f'<g clip-path="url(#{cid})">{text(s, x, y, size, fill, ch, weight)}</g>', begin + dur

def cursor(x, y, size, ch, begin, fill=None):
    col = fill or C["pur2"]
    box = f'x="{x:.2f}" y="{y-size*0.82:.2f}" width="{ch:.2f}" height="{size*0.95:.2f}" fill="{col}"'
    if PREVIEW:
        return f'<rect {box}/>'
    return (f'<rect {box} opacity="0">'
            f'<animate attributeName="opacity" values="0;1" begin="{begin:.2f}s" dur="0.01s" fill="freeze"/>'
            f'<animate attributeName="opacity" values="1;1;0;0" begin="{begin:.2f}s" dur="1.06s" '
            f'repeatCount="indefinite"/></rect>')

def svg(w, h, body, label="terminal"):
    return ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}">'
            f'{body}</svg>')
