#!/usr/bin/env python3
"""Собирает «Места, где я не был» из папок-мечт.

Каждая мечта — папка рядом с этой (например «Уганда/») с файлом «мечта.md»
и папкой «доска/» с картинками. Скрипт сам находит все такие папки.

Запуск:
  PDF:  python3 -I make_mockup.py <папка с GeoJSON> <выход.html> '<json высот>'
  веб:  python3 -I make_mockup.py <папка с GeoJSON> <выход.html> '{}' web
"""
import json, math, sys, html, os, base64, mimetypes, re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA, OUT = sys.argv[1], sys.argv[2]
HEIGHTS = json.loads(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else {}
WEB = len(sys.argv) > 4 and sys.argv[4] == "web"

# ---------- чтение мечты из «мечта.md» ----------
def parse_dream(path):
    """Простой разбор: «# Заголовок», строки «ключ: значение», разделы «## …», пункты «- …»."""
    d = {"title": "", "meta": {}, "sections": {}}
    cur = None
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if line.startswith("# ") and not d["title"]:
                d["title"] = line[2:].strip()
            elif line.startswith("## "):
                cur = line[3:].strip()
                d["sections"][cur] = {"text": [], "items": [], "meta": {}}
            elif cur is None:
                m = re.match(r"^([^:]+):\s*(.*)$", line)
                if m:
                    d["meta"][m.group(1).strip()] = m.group(2).strip()
            else:
                sec = d["sections"][cur]
                if line.startswith("- "):
                    sec["items"].append(line[2:].strip())
                else:
                    m = re.match(r"^([^:|]+):\s*(.*)$", line)
                    if m and len(m.group(1)) < 20:
                        sec["meta"][m.group(1).strip()] = m.group(2).strip()
                    elif line.strip():
                        sec["text"].append(line.strip())
    return d

def load_dreams():
    dreams = []
    for name in sorted(os.listdir(ROOT)):
        p = os.path.join(ROOT, name, "мечта.md")
        if not os.path.isfile(p):
            continue
        d = parse_dream(p)
        m = d["meta"]
        pts = []
        for it in d["sections"].get("Точки", {}).get("items", []):
            parts = [x.strip() for x in it.split("|")]
            lon, lat = (float(v) for v in parts[0].split(","))
            kind = "hub" if len(parts) > 2 and parts[2] in ("узел", "hub") else "main"
            pts.append((lon, lat, parts[1], kind))
        routes = []
        for it in d["sections"].get("Маршруты", {}).get("items", []):
            parts = [x.strip() for x in it.split("|")] + ["", "", ""]
            cls = "warn" if parts[2] in ("дорого", "warn") else "old" if parts[2] in ("устарел", "old") else "ok"
            routes.append((parts[0], parts[1], cls, parts[3]))
        bbox = tuple(float(v) for v in m.get("карта", "0,0,1,1").split(","))
        dreams.append({
            "folder": name,
            "slug": m.get("ключ", name.lower()),
            "country": m.get("страна", ""),
            "title": d["title"] or name,
            "subtitle": m.get("подзаголовок", ""),
            "short": m.get("коротко", ""),
            "ready": m.get("готова", "нет").lower() in ("да", "yes", "true", "1"),
            "bbox": bbox,
            "lakes": m.get("озёра", "да").lower() == "да",
            "rivers": m.get("реки", "нет").lower() == "да",
            "order": int(m.get("порядок", "99")),
            "why": " ".join(d["sections"].get("Почему туда", {}).get("text", [])),
            "points": pts,
            "books": d["sections"].get("Что привело", {}).get("items", []),
            "season": d["sections"].get("Когда и почём", {}).get("meta", {}).get("сезон", ""),
            "budget": d["sections"].get("Когда и почём", {}).get("meta", {}).get("бюджет", ""),
            "routes": routes,
        })
    dreams.sort(key=lambda x: (x["order"], x["title"]))
    return dreams

DREAMS = load_dreams()
READY = {d["country"] for d in DREAMS if d["ready"]}
WORKING = {d["country"] for d in DREAMS if not d["ready"]}
SLUGS = {d["country"]: d["slug"] for d in DREAMS}

# ---------- доска картинок ----------
def board_cards(folder):
    d = os.path.join(ROOT, folder, "доска")
    cards = []
    if os.path.isdir(d):
        for name in sorted(os.listdir(d)):
            ext = os.path.splitext(name)[1].lower()
            if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                continue
            with open(os.path.join(d, name), "rb") as f:
                data = base64.b64encode(f.read()).decode()
            mime = mimetypes.guess_type(name)[0] or "image/jpeg"
            cap = os.path.splitext(name)[0]
            cap = cap.split(" ", 1)[1] if cap[:2].isdigit() and " " in cap else cap
            cards.append(f'<figure><img src="data:{mime};base64,{data}" alt=""><figcaption>{html.escape(cap)}</figcaption></figure>')
    sp = os.path.join(d, "источники.txt")
    if WEB and cards and os.path.exists(sp):
        srcs = []
        lines = [l.rstrip() for l in open(sp, encoding="utf-8")]
        for i, l in enumerate(lines):
            if l and not l.startswith(" ") and i + 2 < len(lines) and lines[i + 1].startswith("  http"):
                nm = os.path.splitext(l.strip())[0]
                nm = nm.split(" ", 1)[1] if nm[:1] in "UP" and nm[1:2] == " " else nm
                nm = nm.split(" ", 1)[1] if nm[:2].isdigit() else nm
                srcs.append(f'<li>{html.escape(nm)} — <a href="{html.escape(lines[i + 1].strip())}">источник</a>, {html.escape(lines[i + 2].strip())}</li>')
        if srcs:
            cards.append('<details class="src"><summary>Откуда картинки</summary><ul>' + "".join(srcs) + '</ul></details>')
    if not cards:
        cards.append('<figure><div class="ph" style="height:28mm">доска пуста</div><figcaption>Положите картинки в папку «доска»</figcaption></figure>')
    return "".join(cards)

# ---------- геоданные ----------
def load(name):
    with open(f"{DATA}/{name}.geojson", encoding="utf-8") as f:
        return json.load(f)

W110 = load("ne_110m_admin_0_countries")
W50 = load("ne_50m_admin_0_countries")
LAKES = load("ne_50m_lakes")
RIVERS = load("ne_50m_rivers_lake_centerlines")

def rings(geom):
    t = geom["type"]
    if t == "Polygon":
        for r in geom["coordinates"]:
            yield r
    elif t == "MultiPolygon":
        for poly in geom["coordinates"]:
            for r in poly:
                yield r
    elif t == "LineString":
        yield geom["coordinates"]
    elif t == "MultiLineString":
        for r in geom["coordinates"]:
            yield r

def path(geom, proj, close=True):
    d = []
    for r in rings(geom):
        pts = [proj(x, y) for x, y in r]
        d.append("M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + ("Z" if close else ""))
    return " ".join(d)

def globe_svg(lon0, lat0, size=600, pad=6):
    """Полушарие в ортографической проекции с центром (lon0, lat0)."""
    R = size / 2 - pad
    cx = cy = size / 2
    la0, lo0 = math.radians(lat0), math.radians(lon0)
    def proj(lon, lat):
        la, lo = math.radians(lat), math.radians(lon)
        cosc = math.sin(la0) * math.sin(la) + math.cos(la0) * math.cos(la) * math.cos(lo - lo0)
        x = math.cos(la) * math.sin(lo - lo0)
        y = math.cos(la0) * math.sin(la) - math.sin(la0) * math.cos(la) * math.cos(lo - lo0)
        if cosc < 0:  # обратная сторона — прижимаем к краю диска
            n = math.hypot(x, y) or 1e-9
            x, y = x / n, y / n
        return cx + x * R, cy - y * R
    def visible(geom):
        for r in rings(geom):
            for lon, lat in r:
                la, lo = math.radians(lat), math.radians(lon)
                if math.sin(la0) * math.sin(la) + math.cos(la0) * math.cos(la) * math.cos(lo - lo0) > 0:
                    return True
        return False
    gid = f"g{int(lon0)}".replace("-", "m")
    parts = [f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">',
             f'<defs><clipPath id="{gid}"><circle cx="{cx}" cy="{cy}" r="{R}"/></clipPath></defs>',
             f'<circle class="sea" cx="{cx}" cy="{cy}" r="{R}"/>',
             f'<g clip-path="url(#{gid})">']
    for lat in range(-60, 90, 30):
        pts = [proj(lon, lat) for lon in range(-180, 181, 3)]
        parts.append('<path class="grat" d="M' + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + '"/>')
    for lon in range(-180, 180, 30):
        pts = [proj(lon, lat) for lat in range(-90, 91, 3)]
        parts.append('<path class="grat" d="M' + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + '"/>')
    for f in W110["features"]:
        n = f["properties"]["ADMIN"]
        if not visible(f["geometry"]):
            continue
        cls = "ready" if n in READY else "working" if n in WORKING else "land"
        go = f' data-go="{SLUGS[n]}"' if n in SLUGS else ""
        parts.append(f'<path class="{cls}"{go} d="{path(f["geometry"], proj)}"/>')
    parts.append(f'</g><circle class="rim" cx="{cx}" cy="{cy}" r="{R}"/></svg>')
    return "\n".join(parts)

def in_bbox(geom, bbox):
    lon0, lat0, lon1, lat1 = bbox
    for r in rings(geom):
        xs = [pt[0] for pt in r]; ys = [pt[1] for pt in r]
        if max(xs) >= lon0 and min(xs) <= lon1 and max(ys) >= lat0 and min(ys) <= lat1:
            return True
    return False

def country_svg(name, bbox, points, lakes=True, rivers=False, size=(600, 600)):
    lon0, lat0, lon1, lat1 = bbox
    SW, SH = size
    k = math.cos(math.radians((lat0 + lat1) / 2))
    s = min(SW / ((lon1 - lon0) * k), SH / (lat1 - lat0))
    ox = (SW - (lon1 - lon0) * k * s) / 2
    oy = (SH - (lat1 - lat0) * s) / 2
    def proj(lon, lat):
        return ox + (lon - lon0) * k * s, oy + (lat1 - lat) * s
    parts = [f'<svg viewBox="0 0 {SW} {SH}" xmlns="http://www.w3.org/2000/svg">']
    for f in W50["features"]:
        if not in_bbox(f["geometry"], bbox):
            continue
        cls = "focus" if f["properties"]["ADMIN"] == name else "neighbor"
        parts.append(f'<path class="{cls}" d="{path(f["geometry"], proj)}"/>')
    if lakes:
        for f in LAKES["features"]:
            if in_bbox(f["geometry"], bbox):
                parts.append(f'<path class="water" d="{path(f["geometry"], proj)}"/>')
    if rivers:
        for f in RIVERS["features"]:
            if in_bbox(f["geometry"], bbox):
                parts.append(f'<path class="river" d="{path(f["geometry"], proj, close=False)}"/>')
    for i, (lon, lat, label, kind) in enumerate(points, 1):
        x, y = proj(lon, lat)
        parts.append(f'<circle class="pt {kind}" cx="{x:.1f}" cy="{y:.1f}" r="11"/>')
        parts.append(f'<text class="ptn" x="{x:.1f}" y="{y + 4.5:.1f}" text-anchor="middle">{i}</text>')
        parts.append(f'<text class="ptl" x="{x + 16:.1f}" y="{y + 5:.1f}">{html.escape(label)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)

# ---------- страницы ----------
PAGE_RULES = []

def page_world():
    h = HEIGHTS.get("world", 216)
    PAGE_RULES.append(f"@page world {{ size: 100mm {h}mm; margin: 0; }}")
    nr, nw = len(READY), len(WORKING)
    stats = f"""
  <div class="stats">
    <div class="ready"><b>{nr}</b><span>{'готова' if nr == 1 else 'готовы'}</span></div>
    <div class="working"><b>{nw}</b><span>в работе</span></div>
    <div><b>{nr + nw}</b><span>{'страна' if nr + nw == 1 else 'страны'}</span></div>
  </div>"""
    globes = f"""
  <div class="globes">
    <div class="globe">{globe_svg(70, 0)}</div>
    <div class="globe">{globe_svg(-92, 0)}</div>
  </div>"""
    if WEB:
        return f"""
<section class="page world" id="world" style="page: world; height: {h}mm">
  <header class="top">
    <h1>Места, где я не был</h1>
    <span class="add" title="Добавить мечту" aria-label="Добавить мечту">+</span>
  </header>{globes}{stats}
</section>"""
    legend = """
  <div class="legend">
    <span><i class="sw ready"></i>Мечта готова</span>
    <span><i class="sw working"></i>Мечта в работе</span>
  </div>"""
    items = "".join(
        f'<li data-go="{d["slug"]}"><span class="dot {"ready" if d["ready"] else "working"}"></span>'
        f'<span class="name">{html.escape(d["title"])}</span>'
        f'<span class="meta">{html.escape(d["short"])} · {len(d["points"])} точки</span></li>'
        for d in DREAMS)
    return f"""
<section class="page world" id="world" style="page: world; height: {h}mm">
  <header class="top">
    <h1>Места, где я не был</h1>
    <p class="sub">Мечты, которые я проработал</p>
  </header>{globes}{legend}{stats}
  <ul class="list">{items}</ul>
  <p class="hint">Нажмите на страну, чтобы открыть мечту</p>
</section>"""

def page_country(d):
    slug = d["slug"]
    height = HEIGHTS.get(slug, 300)
    PAGE_RULES.append(f"@page {slug} {{ size: 100mm {height}mm; margin: 0; }}")
    svg = country_svg(d["country"], d["bbox"], d["points"], lakes=d["lakes"], rivers=d["rivers"])
    pts = "".join(f'<li><span class="num">{i}</span>{html.escape(p[2])}</li>' for i, p in enumerate(d["points"], 1))
    bks = "".join(f'<li>{html.escape(b)}</li>' for b in d["books"])
    rts = "".join(
        f'<li><div class="rrow"><span class="link">{html.escape(r[0])}</span><span class="tag {r[2]}">{html.escape(r[1])}</span></div>'
        + (f'<div class="rmeta">{html.escape(r[3])}</div>' if r[3] else "") + '</li>'
        for r in d["routes"])
    return f"""
<section class="page country" id="{slug}" style="page: {slug}; height: {height}mm">
  <header class="top row">
    <span class="back" data-go="world">‹ Карта</span>
    <h1>{html.escape(d["title"])}</h1>
  </header>
  <p class="sub">{html.escape(d["subtitle"])}</p>
  <div class="map">{svg}</div>
  <div class="board">{board_cards(d["folder"])}</div>
  <h2>Почему туда</h2>
  <p class="text">{html.escape(d["why"])}</p>
  <h2>Точки</h2>
  <ol class="points">{pts}</ol>
  <h2>Что привело</h2>
  <ul class="books">{bks}</ul>
  <h2>Когда и почём</h2>
  <div class="facts">
    <div><span class="fl">Сезон</span><span class="fv">{html.escape(d["season"])}</span></div>
    <div><span class="fl">Бюджет</span><span class="fv">{html.escape(d["budget"])}</span></div>
  </div>
  <h2>Маршруты компаний</h2>
  <ul class="routes">{rts}</ul>
  <div class="toggle {'on' if d['ready'] else 'off'}">
    <span>Мечта готова</span>
    <i></i>
  </div>
</section>"""

CSS = """
@page { size: 100mm 216mm; margin: 0; }

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: #f4efe6; }
body { font-family: -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif; color: #2a2622; }
.page { width: 100mm; height: 216mm; padding: 10mm 7mm 8mm; page-break-after: always; background: #f4efe6; overflow: hidden; position: relative; }
.page:last-child { page-break-after: auto; }
h1 { font-size: 22px; margin: 0; letter-spacing: -0.3px; }
h2 { font-size: 10px; text-transform: uppercase; letter-spacing: 1.2px; color: #8a7f72; margin: 8px 0 3px; }
.sub { margin: 2px 0 8px; color: #6e655a; font-size: 13px; }
.top.row { display: flex; align-items: baseline; gap: 10px; }
.back { color: #b5532f; font-size: 14px; }
.map svg { width: 100%; height: auto; display: block; }
.land { fill: #e2d9cc; stroke: #f4efe6; stroke-width: 0.6; }
.ready { fill: #b5532f; stroke: #f4efe6; stroke-width: 0.6; }
.working { fill: #e9b9a3; stroke: #b5532f; stroke-width: 0.8; }
.legend { display: flex; gap: 16px; font-size: 11px; color: #6e655a; margin: 8px 0 0; }
.sw { display: inline-block; width: 12px; height: 12px; border-radius: 3px; margin-right: 5px; vertical-align: -2px; }
.sw.ready { background: #b5532f; }
.sw.working { background: #e9b9a3; }
.stats { display: flex; gap: 8px; margin: 14px 0 10px; }
.stats div { flex: 1; background: #fff; border-radius: 10px; padding: 8px 6px; text-align: center; }
.stats b { display: block; font-size: 22px; color: #b5532f; }
.stats span { font-size: 10px; color: #8a7f72; text-transform: uppercase; letter-spacing: 1px; }
.list { list-style: none; margin: 0; padding: 0; }
.list li { display: grid; grid-template-columns: 14px 1fr; column-gap: 8px; background: #fff; border-radius: 10px; padding: 9px 10px; margin-bottom: 6px; }
.dot { width: 10px; height: 10px; border-radius: 50%; margin-top: 4px; }
.dot.ready { background: #b5532f; }
.dot.working { background: #e9b9a3; }
.name { font-size: 14px; font-weight: 600; }
.meta { grid-column: 2; font-size: 11px; color: #8a7f72; }
.hint { margin: 10px 0 0; text-align: center; font-size: 11px; color: #a1978a; }
.globes { margin: 6px 0 0; }
.globe svg { width: 100%; height: auto; display: block; }
.sea { fill: #e4e9e8; }
.rim { fill: none; stroke: #cfc6b8; stroke-width: 1.2; }
.grat { fill: none; stroke: #fff; stroke-width: 0.6; }

.country .map { background: #fff; border-radius: 12px; overflow: hidden; }
.country .map svg { height: 58mm; }
.neighbor { fill: #ebe4d8; stroke: #fff; stroke-width: 1; }
.focus { fill: #f9d9c9; stroke: #b5532f; stroke-width: 1.5; }
.water { fill: #cfe1ea; stroke: none; }
.river { fill: none; stroke: #9fc0cf; stroke-width: 1.2; }
.pt { stroke: #fff; stroke-width: 2.5; }
.pt.main { fill: #b5532f; }
.pt.hub { fill: #6e655a; }
.ptn { fill: #fff; font-size: 12px; font-weight: 700; font-family: -apple-system, Helvetica, Arial; }
.ptl { fill: #2a2622; font-size: 13px; font-weight: 600; font-family: -apple-system, Helvetica, Arial; paint-order: stroke; stroke: #fff; stroke-width: 3px; stroke-linejoin: round; }
.text { font-size: 12px; line-height: 1.35; margin: 0; }
.points { list-style: none; margin: 0; padding: 0; font-size: 12px; }
.points li { display: flex; align-items: center; gap: 8px; padding: 2px 0; }
.num { display: inline-flex; width: 18px; height: 18px; border-radius: 50%; background: #b5532f; color: #fff; font-size: 11px; font-weight: 700; align-items: center; justify-content: center; }
.books, .routes { margin: 0; padding: 0; list-style: none; font-size: 12px; }
.books li { padding: 2px 0; }
.routes li { padding: 2px 0; }
.rrow { display: flex; justify-content: space-between; align-items: center; gap: 6px; }
.rmeta { font-size: 10px; color: #8a7f72; margin-top: 1px; }
.link { color: #3b6ea5; text-decoration: underline; }
.tag { font-size: 10px; padding: 2px 6px; border-radius: 6px; background: #ece6dc; color: #6e655a; white-space: nowrap; }
.tag.warn { background: #f9d9c9; color: #8a3a1f; }
.tag.ok { background: #e3eadb; color: #3f5a2e; }
.facts { display: flex; gap: 6px; }
.facts div { flex: 1; background: #fff; border-radius: 10px; padding: 7px 9px; }
.fl { display: block; font-size: 9px; text-transform: uppercase; letter-spacing: 1px; color: #8a7f72; }
.fv { display: block; font-size: 11.5px; line-height: 1.3; margin-top: 2px; }
.board { column-count: 2; column-gap: 6px; margin-top: 6px; }
.board figure { break-inside: avoid; margin: 0 0 6px; background: #fff; border-radius: 10px; overflow: hidden; }
.board img { width: 100%; display: block; }
.board .ph { display: flex; align-items: center; justify-content: center; background: #ddd5c8; color: #a1978a; font-size: 10px; text-transform: uppercase; letter-spacing: 1px; }
.board figcaption { font-size: 10.5px; line-height: 1.25; padding: 5px 7px 6px; color: #2a2622; }
.toggle { margin-top: 8px; display: flex; justify-content: space-between; align-items: center; background: #fff; border-radius: 12px; padding: 10px 12px; font-size: 14px; font-weight: 600; }
.toggle i { width: 42px; height: 24px; border-radius: 12px; background: #d9d2c6; position: relative; }
.toggle i::after { content: ""; position: absolute; top: 2px; left: 2px; width: 20px; height: 20px; border-radius: 50%; background: #fff; }
.toggle.on i { background: #b5532f; }
.toggle.on i::after { left: 20px; }
"""

WEBHEAD = """
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icon-180.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Места">
<meta name="theme-color" content="#f4efe6">""" if WEB else ""

WEBTAIL = """
<style>
html, body { background: #e9e2d6; overflow-x: hidden; }
.page { height: auto !important; min-height: 100vh; width: 100%; max-width: 440px; margin: 0 auto; padding: 14px 16px 24px; page-break-after: auto; }
.page:not(.active) { display: none; }
[data-go] { cursor: pointer; }
.toggle { cursor: pointer; }
.src { margin: 4px 0 2px; font-size: 10.5px; color: #8a7f72; column-span: all; break-inside: avoid; }
.src summary { cursor: pointer; }
.src ul { padding-left: 16px; margin: 4px 0; }
.src a { color: #3b6ea5; }
.globe svg, .map svg { max-height: none; }
.world { min-height: 100vh; padding-top: 10px; }
.world h1 { font-size: 20px; }
.world .top { display: flex; align-items: center; justify-content: space-between; }
.add { width: 30px; height: 30px; border-radius: 50%; background: #b5532f; color: #fff; font-size: 24px; line-height: 29px; text-align: center; font-weight: 300; cursor: pointer; }
.world .stats div.ready { background: #b5532f; }
.world .stats div.ready b, .world .stats div.ready span { color: #fff; }
.world .stats div.working { background: #e9b9a3; }
.world .stats div.working b, .world .stats div.working span { color: #7a3419; }
.world .globes { display: flex; flex-direction: column; align-items: center; gap: 0; }
.world .globe { width: min(100%, 40vh); width: min(100%, 41svh); }
.world .stats { margin: 4px 0 0; gap: 6px; }
.world .stats div { display: flex; align-items: baseline; justify-content: center; gap: 5px; padding: 6px 4px; border-radius: 9px; }
.world .stats b { display: inline; font-size: 15px; }
.world .stats span { font-size: 9.5px; letter-spacing: 0.6px; }
</style>
<script>
(function () {
  var pages = document.querySelectorAll('.page');
  function show() {
    var id = (location.hash || '#world').slice(1);
    var found = false;
    pages.forEach(function (p) { var on = p.id === id; p.classList.toggle('active', on); found = found || on; });
    if (!found) pages[0].classList.add('active');
    window.scrollTo(0, 0);
  }
  document.querySelectorAll('[data-go]').forEach(function (el) {
    el.addEventListener('click', function () { location.hash = el.dataset.go; });
  });
  document.querySelectorAll('.toggle').forEach(function (t) {
    var key = 'ready:' + t.closest('.page').id;
    try { if (localStorage.getItem(key) !== null) t.classList.toggle('on', localStorage.getItem(key) === '1'); } catch (e) {}
    t.addEventListener('click', function () {
      t.classList.toggle('on');
      try { localStorage.setItem(key, t.classList.contains('on') ? '1' : '0'); } catch (e) {}
    });
  });
  window.addEventListener('hashchange', show);
  show();
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('sw.js').catch(function () {});
  }
})();
</script>
""" if WEB else ""

WORLD = page_world()
COUNTRIES = "".join(page_country(d) for d in DREAMS)
doc = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Места, где я не был</title>{WEBHEAD}<style>{CSS}{chr(10).join(PAGE_RULES)}</style></head>
<body>{WORLD}{COUNTRIES}
<script>document.querySelectorAll('.page.country, .page.world').forEach(s => s.dataset.h = Math.ceil(s.scrollHeight / 96 * 25.4) + 6);</script>
{WEBTAIL}</body></html>"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(doc)
print("written", OUT, len(doc), "bytes;", len(DREAMS), "dreams:", ", ".join(d["title"] for d in DREAMS))
