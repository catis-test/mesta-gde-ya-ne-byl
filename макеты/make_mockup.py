#!/usr/bin/env python3
"""Собирает HTML-макет приложения «Места, где я не был»: мир, Уганда, Перу.
Запуск: python3 -I make_mockup.py <папка с GeoJSON> <выходной html>
"""
import json, math, sys, html, os, base64, mimetypes

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

def board_cards(country_dir, placeholders):
    """Карточки доски: картинки из папки «<страна>/доска», иначе заглушки."""
    d = os.path.join(ROOT, country_dir, "доска")
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
            cards.append(f'<figure><img src="data:{mime};base64,{data}"><figcaption>{html.escape(cap)}</figcaption></figure>')
    srcs = []
    sp = os.path.join(d, "источники.txt")
    if WEB and cards and os.path.exists(sp):
        lines = [l.rstrip() for l in open(sp, encoding="utf-8")]
        for i, l in enumerate(lines):
            if l and not l.startswith(" ") and i + 2 < len(lines) and lines[i+1].startswith("  http"):
                nm = os.path.splitext(l.strip())[0]
                nm = nm.split(" ", 1)[1] if nm[:1] in "UP" and nm[1:2] == " " else nm
                nm = nm.split(" ", 1)[1] if nm[:2].isdigit() else nm
                srcs.append(f'<li>{html.escape(nm)} — <a href="{html.escape(lines[i+1].strip())}">источник</a>, {html.escape(lines[i+2].strip())}</li>')
        if srcs:
            cards.append('<details class="src"><summary>Откуда картинки</summary><ul>' + "".join(srcs) + '</ul></details>')
    if not cards:
        for cap, h in placeholders:
            cards.append(f'<figure><div class="ph" style="height:{h}mm">{html.escape(cap.split(":")[0])}</div><figcaption>{html.escape(cap)}</figcaption></figure>')
    return "".join(cards)

DATA, OUT = sys.argv[1], sys.argv[2]
HEIGHTS = json.loads(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else {}
WEB = len(sys.argv) > 4 and sys.argv[4] == "web"
SLUGS = {"Uganda": "uganda", "Peru": "peru"}

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

# ---------- мир (равнопромежуточная проекция, без Антарктиды) ----------
WW, WH = 1000, 520
LAT_TOP, LAT_BOT = 84, -58
def proj_world(lon, lat):
    x = (lon + 180) / 360 * WW
    y = (LAT_TOP - lat) / (LAT_TOP - LAT_BOT) * WH
    return x, y

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
    parts = [f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">',
             f'<defs><clipPath id="g{int(lon0)}"><circle cx="{cx}" cy="{cy}" r="{R}"/></clipPath></defs>',
             f'<circle class="sea" cx="{cx}" cy="{cy}" r="{R}"/>',
             f'<g clip-path="url(#g{int(lon0)})">']
    # сетка
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

READY = {"Uganda"}          # мечта готова — заливка
WORKING = {"Peru"}          # в работе — контур

def world_svg():
    parts = [f'<svg viewBox="0 0 {WW} {WH}" xmlns="http://www.w3.org/2000/svg">']
    for f in W110["features"]:
        n = f["properties"]["ADMIN"]
        if n == "Antarctica":
            continue
        cls = "ready" if n in READY else "working" if n in WORKING else "land"
        parts.append(f'<path class="{cls}" d="{path(f["geometry"], proj_world)}"/>')
    parts.append("</svg>")
    return "\n".join(parts)

# ---------- страна ----------
def in_bbox(geom, bbox):
    """Пересекается ли геометрия с окном карты (грубо, по крайним точкам)."""
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
    sx = SW / ((lon1 - lon0) * k)
    sy = SH / (lat1 - lat0)
    s = min(sx, sy)
    ox = (SW - (lon1 - lon0) * k * s) / 2
    oy = (SH - (lat1 - lat0) * s) / 2
    def proj(lon, lat):
        return ox + (lon - lon0) * k * s, oy + (lat1 - lat) * s
    parts = [f'<svg viewBox="0 0 {SW} {SH}" xmlns="http://www.w3.org/2000/svg">']
    for f in W50["features"]:
        n = f["properties"]["ADMIN"]
        if not in_bbox(f["geometry"], bbox):
            continue
        cls = "focus" if n == name else "neighbor"
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
        parts.append(f'<text class="ptn" x="{x:.1f}" y="{y+4.5:.1f}" text-anchor="middle">{i}</text>')
        parts.append(f'<text class="ptl" x="{x+16:.1f}" y="{y+5:.1f}">{html.escape(label)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)

UGANDA_PTS = [
    (32.44, 0.04,  "Энтеббе (EBB)", "hub"),
    (29.65, -1.05, "Бвинди — горные гориллы", "main"),
    (30.35, 0.56,  "Кибале, Каньявара — шимпанзе Рэнгема", "main"),
]
PERU_PTS = [
    (-77.11, -12.02, "Лима, пересадка", "hub"),
    (-69.19, -12.59, "Пуэрто-Мальдонадо (PEM)", "hub"),
    (-70.35, -11.65, "Станция рейнджеров, Лас-Пьедрас", "main"),
]

def page_world():
    h = HEIGHTS.get("world", 216)
    PAGE_RULES.append(f"@page world {{ size: 100mm {h}mm; margin: 0; }}")
    legend = """
  <div class="legend">
    <span><i class="sw ready"></i>Готова</span>
    <span><i class="sw working"></i>В работе</span>
  </div>"""
    stats = """
  <div class="stats">
    <div><b>1</b><span>готова</span></div>
    <div><b>1</b><span>в работе</span></div>
    <div><b>2</b><span>страны</span></div>
  </div>"""
    globes = f"""
  <div class="globes">
    <div class="globe">{globe_svg(70, 0)}</div>
    <div class="globe">{globe_svg(-92, 0)}</div>
  </div>"""
    if WEB:
        return f"""
<section class="page world" id="world" style="page: world; height: {h}mm">
  <header class="top row">
    <h1>Места, где я не был</h1>{legend}
  </header>{globes}{stats}
</section>"""
    return f"""
<section class="page world" id="world" style="page: world; height: {h}mm">
  <header class="top">
    <h1>Места, где я не был</h1>
    <p class="sub">Мечты, которые я проработал</p>
  </header>{globes}{legend}{stats}
  <ul class="list">
    <li data-go="uganda"><span class="dot ready"></span><span class="name">Уганда</span><span class="meta">гориллы и шимпанзе · 3 точки</span></li>
    <li data-go="peru"><span class="dot working"></span><span class="name">Перу</span><span class="meta">верховья Амазонки · 3 точки</span></li>
  </ul>
  <p class="hint">Нажмите на страну, чтобы открыть мечту</p>
</section>"""

PAGE_RULES = []

def page_country(title, subtitle, svg, ready, text, points, books, routes, season="", budget="", board="", slug="c", height=300):
    height = HEIGHTS.get(slug, height)
    PAGE_RULES.append(f"@page {slug} {{ size: 100mm {height}mm; margin: 0; }}")
    pts = "".join(f'<li><span class="num">{i}</span>{html.escape(p[2])}</li>' for i, p in enumerate(points, 1))
    bks = "".join(f'<li>{html.escape(b)}</li>' for b in books)
    rts = "".join(
        f'<li><div class="rrow"><span class="link">{html.escape(r[0])}</span><span class="tag {r[2]}">{html.escape(r[1])}</span></div>'
        + (f'<div class="rmeta">{html.escape(r[3])}</div>' if len(r) > 3 and r[3] else "") + '</li>'
        for r in routes)
    toggle = "on" if ready else "off"
    return f"""
<section class="page country" id="{slug}" style="page: {slug}; height: {height}mm">
  <header class="top row">
    <span class="back" data-go="world">‹ Карта</span>
    <h1>{html.escape(title)}</h1>
  </header>
  <p class="sub">{html.escape(subtitle)}</p>
  <div class="map">{svg}</div>
  <div class="board">{board}</div>
  <h2>Почему туда</h2>
  <p class="text">{text}</p>
  <h2>Точки</h2>
  <ol class="points">{pts}</ol>
  <h2>Что привело</h2>
  <ul class="books">{bks}</ul>
  <h2>Когда и почём</h2>
  <div class="facts">
    <div><span class="fl">Сезон</span><span class="fv">{html.escape(season)}</span></div>
    <div><span class="fl">Бюджет</span><span class="fv">{html.escape(budget)}</span></div>
  </div>
  <h2>Маршруты компаний</h2>
  <ul class="routes">{rts}</ul>
  <div class="toggle {toggle}">
    <span>Мечта готова</span>
    <i></i>
  </div>
</section>"""

UG = page_country(
    "Уганда", "Гориллы и шимпанзе за одну поездку",
    country_svg("Uganda", (29.3, -1.6, 35.2, 4.4), UGANDA_PTS, lakes=True),
    True,
    "Поход к горным гориллам в Бвинди и в той же поездке — шимпанзе в Кибале, "
    "где Рэнгем с 1987 года ведёт проект на станции Каньявара. Сюда меня привели "
    "его книга и история, а ещё Кропоткин, у которого гориллы должны были "
    "исчезнуть, но не исчезли. Пермит к гориллам $800 за трек, к шимпанзе ≈$250.",
    UGANDA_PTS,
    ["Ричард Рэнгем — «Парадокс добродетели»",
     "Пётр Кропоткин — «Взаимопомощь как фактор эволюции»"],
    [("Pangolin Photo Safaris — фототур", "9 дн · $14 450", "warn",
      "2 трека гориллы, 2 дня шимпанзе · китоглавы на Мабамбе · до 7 чел."),
     ("Cheesemans, США", "12 дн · $16 300", "warn",
      "3 трека гориллы, 2 дня Кибале · группа 7"),
     ("Natural Habitat, США", "10 дн · ≈$20 000", "warn",
      "база $15 695 + пермиты $2 100 + перелёты · 2 + 2 трека · до 12"),
     ("Gate 1 Travel, США", "11 дн · $7 099", "ok",
      "1 трек гориллы + 1 шимпанзе · Мёрчисон, Куин-Элизабет · до 18"),
     ("Geotours, Израиль, на иврите", "12 дн · $8 750", "ok",
      "1 + 1 трек · с перелётом из Тель-Авива · группа от 12"),
     ("Mermar Safaris, Уганда", "10 дн · €3 649", "ok",
      "1 + 1 трек · до 7 в машине · пермиты уточнить")],
    season="Сухо июнь–сентябрь и декабрь–февраль. Дожди март–май дешевле",
    budget="Группой $3 600–20 000 без перелёта, 9–12 дней. Пермиты: гориллы $800 за трек, шимпанзе ≈$250",
    board=board_cards("Уганда", [
        ("Обложка: Рэнгем, «Парадокс добродетели»", 34),
        ("Фото: горная горилла, Бвинди", 22),
        ("Видео: шимпанзе Каньявары", 18),
        ("Обложка: Кропоткин, «Взаимопомощь»", 30),
        ("Фото: китоглав на Мабамбе", 26),
    ]),
    slug="uganda", height=372,
)

PE = page_country(
    "Перу", "Лас-Пьедрас, к рейнджерам Junglekeepers",
    country_svg("Peru", (-81.6, -18.6, -68.4, 0.2), PERU_PTS, lakes=True, rivers=True),
    False,
    "После «Mother of God» Пола Розоли. Его организация Junglekeepers выкупает "
    "землю в коридоре реки Лас-Пьедрас. Их партнёр Tamandua Expeditions возит "
    "волонтёров к рейнджерам и водит искать анаконду. Все маршруты начинаются "
    "в Пуэрто-Мальдонадо.",
    PERU_PTS,
    ["Пол Розоли — «Mother of God»"],
    [("Become a Junglekeeper — неделя с рейнджерами", "8 дн · $2 795", "ok",
      "патрули с рейнджерами, станция на Лас-Пьедрас · 5–10 чел."),
     ("Herping — поиск анаконды и кайманов", "8 дн · $2 850", "ok",
      "анаконда, 4 вида кайманов, бушмейстер · до 10 чел."),
     ("Приют Amazon Shelter + Junglekeepers", "21 дн · $3 895", "ok",
      "2 недели в приюте + 5 ночей у рейнджеров · тяжёлая работа")],
    season="Выезды круглый год. Суше май–октябрь (проверить)",
    budget="$2 800–3 900 без перелёта, 8–21 день. Плюс перелёт до Пуэрто-Мальдонадо и страховка",
    board=board_cards("Перу", [
        ("Обложка: Розоли, «Mother of God»", 34),
        ("Видео: поиск анаконды", 18),
        ("Фото: Лас-Пьедрас с лодки", 24),
        ("Фото: рейнджеры Junglekeepers", 26),
    ]),
    slug="peru", height=300,
)

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
.map.world { margin: 10px -4mm 0; }
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
.globe { position: relative; }
.globe svg { width: 100%; height: auto; display: block; }
.gl { position: absolute; left: 4mm; top: 3mm; font-size: 10px; text-transform: uppercase; letter-spacing: 1.2px; color: #8a7f72; }
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
.tag { font-size: 10px; padding: 2px 6px; border-radius: 6px; background: #ece6dc; color: #6e655a; }
.tag.old { background: #ece6dc; }
.tag.warn { background: #f9d9c9; color: #8a3a1f; }
.tag.ok { background: #e3eadb; color: #3f5a2e; white-space: nowrap; }
.facts { display: flex; gap: 6px; }
.facts div { flex: 1; background: #fff; border-radius: 10px; padding: 7px 9px; }
.fl { display: block; font-size: 9px; text-transform: uppercase; letter-spacing: 1px; color: #8a7f72; }
.fv { display: block; font-size: 11.5px; line-height: 1.3; margin-top: 2px; }
.board { column-count: 2; column-gap: 6px; margin-top: 6px; }
.board figure { break-inside: avoid; margin: 0 0 6px; background: #fff; border-radius: 10px; overflow: hidden; }
.board img { width: 100%; display: block; }
.board .ph { display: flex; align-items: center; justify-content: center; background: #ddd5c8; color: #a1978a; font-size: 10px; text-transform: uppercase; letter-spacing: 1px; }
.board figcaption { font-size: 10.5px; line-height: 1.25; padding: 5px 7px 6px; color: #2a2622; }
.photos { display: flex; gap: 6px; }
.photos div { flex: 1; height: 20mm; border-radius: 8px; background: #ddd5c8; color: #a1978a; font-size: 11px; display: flex; align-items: center; justify-content: center; }
.toggle { margin-top: 8px; display: flex; justify-content: space-between; align-items: center; background: #fff; border-radius: 12px; padding: 10px 12px; font-size: 14px; font-weight: 600; }
.toggle i { width: 42px; height: 24px; border-radius: 12px; background: #d9d2c6; position: relative; }
.toggle i::after { content: ""; position: absolute; top: 2px; left: 2px; width: 20px; height: 20px; border-radius: 50%; background: #fff; }
.toggle.on i { background: #b5532f; }
.toggle.on i::after { left: 20px; }
"""

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
.world .top.row { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin: 0 0 2px; }
.world h1 { font-size: 19px; }
.world .legend { margin: 0; gap: 10px; font-size: 10.5px; white-space: nowrap; }
.world .globes { display: flex; flex-direction: column; align-items: center; gap: 0; }
.world .globe { width: min(100%, 44vh); }
.world .stats { margin: 6px 0 0; }
.world .stats div { padding: 6px 4px; }
.world .stats b { font-size: 18px; }
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
})();
</script>
""" if WEB else ""

WORLD = page_world()
doc = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Места, где я не был — макет</title><style>{CSS}{chr(10).join(PAGE_RULES)}</style></head>
<body>{WORLD}{UG}{PE}
<script>document.querySelectorAll('.page.country, .page.world').forEach(s => s.dataset.h = Math.ceil(s.scrollHeight / 96 * 25.4) + 6);</script>
{WEBTAIL}</body></html>"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(doc)
print("written", OUT, len(doc), "bytes")
