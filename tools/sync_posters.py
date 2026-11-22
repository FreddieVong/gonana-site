#!/usr/bin/env python3
"""Weekly: copy this week's posters from the venue app into the site as light web copies
(540/1024 px, WebP + JPG; app originals untouched), rewrite the page's fallback nights, then
refresh the prerendered Event JSON-LD and the tonight-poster preload.
Usage: python3 tools/sync_posters.py [week.json] [--now ISO] [--dry-run DIR]
  week.json  = a saved app response, for testing without the network
  --now      = treat this ISO datetime as now (e.g. 2026-11-23T06:01:00+08:00)
  --dry-run  = write index.html and posters into DIR; do not change the repo

22 Nov 2026: only nights of THIS week (Mon to Sun, the night runs till 6am MYT) are used. If the app has
no posters for this week and the page still shows a past week, the page gets 7 plain nights for this week
("Live music nightly, <start> to <end>") and no events, so no stale week is ever left on the site.
If a checked-in override exists for this week (tools/lineup-overrides/YYYY-MM-DD.json, the Monday),
that override is used instead of the plain nights, so a week can still go live when the app has no
gigs yet. If the app does return posters for the week, the app wins and the override is ignored.
"""
import argparse, re, json, io, datetime, pathlib, shutil, subprocess, urllib.request, sys
from PIL import Image

repo = pathlib.Path(__file__).resolve().parent.parent
MO = "jan feb mar apr may jun jul aug sep oct nov dec".split()
WD = "mon tue wed thu fri sat sun".split()
WDN = "Mon Tue Wed Thu Fri Sat Sun".split()
MON = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
MYT = datetime.timezone(datetime.timedelta(hours=8))
POSTER_SIZES = (540, 1024)


def parse_now(s):
    if not s:
        return datetime.datetime.now(datetime.timezone.utc)
    t = datetime.datetime.fromisoformat(s)
    if t.tzinfo is None:
        t = t.replace(tzinfo=MYT)
    return t.astimezone(datetime.timezone.utc)


def clock(hh, mm):
    hh = int(hh)
    return f"{hh % 12 or 12}{'' if mm == '00' else ':' + mm}{'pm' if hh >= 12 else 'am'}"


def stem_for(d):
    return f"{WD[d.weekday()]}-{d.day}{MO[d.month-1]}"


def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "site-sync"}), timeout=30).read()


def night_div(date, names, stem, width, height):
    d = datetime.date.fromisoformat(date)
    names = (names or "").replace('"', "&quot;")
    alt = f"Poster, {WDN[d.weekday()]} {d.day} {MON[d.month-1]}" + (f": {names}" if names else "")
    return (
        f'<div class="night" data-date="{date}" data-names="{names}">'
        f'<a href="assets/lineup/{stem}-1024.jpg" target="_blank" rel="noopener"><picture>'
        f'<source data-defer type="image/webp" data-srcset="assets/lineup/{stem}-540.webp 540w, assets/lineup/{stem}-1024.webp 1024w" sizes="(min-width:900px) 440px, 92vw">'
        f'<img data-defer data-src="assets/lineup/{stem}-1024.jpg" data-srcset="assets/lineup/{stem}-540.jpg 540w, assets/lineup/{stem}-1024.jpg 1024w" sizes="(min-width:900px) 440px, 92vw" width="{width}" height="{height}" loading="lazy" decoding="async" alt="{alt}">'
        f"</picture></a></div>"
    )


def save_from_image(im, dest_dir, stem):
    keep = set()
    for w in POSTER_SIZES:
        r = im if im.width <= w else im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
        r.save(dest_dir / f"{stem}-{w}.webp", "WEBP", quality=82, method=6)
        r.save(dest_dir / f"{stem}-{w}.jpg", "JPEG", quality=82, optimize=True, progressive=True)
        keep |= {f"{stem}-{w}.webp", f"{stem}-{w}.jpg"}
    width = min(im.width, 1024)
    height = round(im.height * 1024 / im.width) if im.width > 1024 else im.height
    return keep, width, height


def copy_override_images(src_dir, dest_dir, stem):
    keep = set()
    for w in POSTER_SIZES:
        for ext in ("webp", "jpg"):
            name = f"{stem}-{w}.{ext}"
            src = src_dir / name
            if not src.is_file():
                sys.exit(f"override poster missing: {src}")
            shutil.copy2(src, dest_dir / name)
            keep.add(name)
    im = Image.open(dest_dir / f"{stem}-1024.jpg")
    return keep, im.width, im.height


def load_override(monday):
    path = repo / "tools" / "lineup-overrides" / f"{monday.isoformat()}.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    img_dir = repo / "assets" / "lineup-overrides" / monday.isoformat()
    nights = []
    for n in data.get("nights") or []:
        date = n.get("date")
        stem = n.get("stem") or (stem_for(datetime.date.fromisoformat(date)) if date else None)
        if not date or not stem:
            sys.exit(f"override {path.name} has a night missing date or stem")
        for w in POSTER_SIZES:
            for ext in ("webp", "jpg"):
                if not (img_dir / f"{stem}-{w}.{ext}").is_file():
                    sys.exit(f"override {path.name} is missing {img_dir / f'{stem}-{w}.{ext}'}")
        nights.append({"date": date, "names": n.get("names") or "", "startTime": n.get("startTime") or "21:00", "stem": stem, "img_dir": img_dir})
    if not nights:
        sys.exit(f"override {path.name} has no nights")
    return nights


ap = argparse.ArgumentParser(description="Sync this week's lineup posters and Event markup")
ap.add_argument("week_json", nargs="?", help="saved app response, for testing without the network")
ap.add_argument("--now", help="ISO datetime to treat as now, e.g. 2026-11-23T06:01:00+08:00")
ap.add_argument("--dry-run", dest="dry_run", metavar="DIR", help="write index.html and posters here; do not change the repo")
args = ap.parse_args()

out_root = pathlib.Path(args.dry_run).resolve() if args.dry_run else repo
if args.dry_run:
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "assets" / "lineup").mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo / "index.html", out_root / "index.html")

idx = out_root / "index.html"
h = idx.read_text(encoding="utf-8")
api = re.search(r'"api": "([^"]+)"', h).group(1)
week = json.loads(pathlib.Path(args.week_json).read_text(encoding="utf-8")) if args.week_json else json.loads(get(api))
cfg = re.search(r'"start": "(\d\d):(\d\d)", "end": "(\d\d):(\d\d)"', h)
NIGHTLY = f"Live music nightly, {clock(*cfg.group(1, 2))} to {clock(*cfg.group(3, 4))}"
now = parse_now(args.now)
night_today = (now + datetime.timedelta(hours=8 - 6)).date()
monday = night_today - datetime.timedelta(days=night_today.weekday())
this_week = {(monday + datetime.timedelta(days=k)).isoformat() for k in range(7)}
app_nights = [n for n in week.get("nights", []) if n.get("date") in this_week and n.get("posterUrl")]

out = out_root / "assets/lineup"
out.mkdir(parents=True, exist_ok=True)
divs, keep, source = [], set(), None

if app_nights:
    source = "app"
    for n in app_nights:
        d = datetime.date.fromisoformat(n["date"])
        stem = stem_for(d)
        im = Image.open(io.BytesIO(get(n["posterUrl"]))).convert("RGB")
        files, width, height = save_from_image(im, out, stem)
        keep |= files
        divs.append(night_div(n["date"], n.get("names") or "", stem, width, height))
else:
    override = load_override(monday)
    if override:
        source = f"override {monday.isoformat()}"
        for n in override:
            if n["date"] not in this_week:
                continue
            files, width, height = copy_override_images(n["img_dir"], out, n["stem"])
            keep |= files
            divs.append(night_div(n["date"], n["names"], n["stem"], width, height))

if not divs:
    shown = re.findall(r'<div class="night" data-date="([\d-]+)"', h)
    if shown and max(shown) >= monday.isoformat():
        print("app has no posters for this week yet; the page already shows this week, nothing changed")
        sys.exit(0)
    divs = [f'<div class="night" data-date="{(monday + datetime.timedelta(days=k)).isoformat()}" data-names=""><p class="soon">{NIGHTLY}</p></div>' for k in range(7)]
    source = "plain"
    print("app has no posters for this week: wrote 7 plain nights (" + NIGHTLY + "), no events")

h, k = re.subn(r'(?:[ \t]*<div class="night" data-date="[^"]*"[^\n]*</div>\n)+', lambda m: "".join("          " + x + "\n" for x in divs), h, count=1)
if not k:
    sys.exit("fallback nights block not found; nothing changed")
idx.write_text(h, encoding="utf-8")
if keep:
    for f in out.iterdir():
        if f.name not in keep and re.match(r"(mon|tue|wed|thu|fri|sat|sun)-\d+[a-z]{3}-(540|1024)\.(webp|jpg)$", f.name):
            f.unlink()
subprocess.run([sys.executable, str(repo / "tools/prerender_events.py"), str(idx)], check=True)
n_posters = sum(1 for d in divs if "<picture>" in d)
print(n_posters, "nights with posters synced from", source if source != "app" else api)
if args.dry_run:
    print("dry-run wrote", idx)
