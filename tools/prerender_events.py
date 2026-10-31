#!/usr/bin/env python3
"""Write this week's MusicEvent JSON-LD into index.html as static HTML (id="events-static"),
from the fallback .night[data-date] posters, so crawlers and AI bots see events without JS.
Run after the weekly line-up refresh:  python3 tools/prerender_events.py"""
import re, json, datetime, pathlib
p = pathlib.Path(__file__).resolve().parent.parent / "index.html"
h = p.read_text(encoding="utf-8")
place = {"@type": "BarOrPub", "@id": "https://gonana.my/#venue", "name": "nana 研酒所",
         "address": {"@type": "PostalAddress", "streetAddress": "2, Jalan SS 13/3A, Subang Jaya Industrial Estate",
                     "addressLocality": "Subang Jaya", "addressRegion": "Selangor", "postalCode": "47500", "addressCountry": "MY"}}
ev = []
for d, names, img in re.findall(r'<div class="night" data-date="([\d-]+)" data-names="([^"]*)"><a href="([^"]+)"', h):
    who = [w.strip() for w in names.split("·") if w.strip()]
    nxt = (datetime.date.fromisoformat(d) + datetime.timedelta(days=1)).isoformat()
    ev.append({"@type": "MusicEvent", "name": ("Live music: " + " · ".join(who)) if who else "Live music at nana",
      "description": (", ".join(who) + " live at nana 研酒所, SS13 Subang Jaya. Live music 9pm–12:15am. 18+ from 8:30pm.").lstrip(", "),
      "startDate": d + "T21:00:00+08:00", "endDate": nxt + "T00:15:00+08:00",
      "eventStatus": "https://schema.org/EventScheduled", "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
      "isAccessibleForFree": True, "image": "https://gonana.my/" + img,
      "performer": [{"@type": "Person", "name": w} for w in who], "location": place,
      "organizer": {"@type": "Organization", "name": "nana 研酒所", "url": "https://gonana.my/"},
      "offers": {"@type": "Offer", "price": "0", "priceCurrency": "MYR", "availability": "https://schema.org/InStock",
                 "url": "https://gonana.my/#" + d, "validFrom": d + "T00:00:00+08:00"}})
block = '<script type="application/ld+json" id="events-static">' + json.dumps({"@context": "https://schema.org", "@graph": ev}, ensure_ascii=False) + '</script>'
h = re.sub(r'\n?<script type="application/ld\+json" id="events-static">.*?</script>', '', h, flags=re.S)
h = h.replace("</head>", block + "\n</head>", 1)
p.write_text(h, encoding="utf-8"); print(len(ev), "events prerendered")
# Keep the tonight-poster preload map in <head> in step with this week's posters.
h = p.read_text(encoding="utf-8")
dates = re.findall(r'<div class="night" data-date="([\d-]+)" data-names="[^"]*"><a href="assets/lineup/(.+?)-1024\.jpg"', h)
h = re.sub(r'(<script id="poster-preload">\(function\(\)\{var m=\{)[^}]*\}', lambda mm: mm.group(1) + ",".join(f'"{d}":"{s}"' for d, s in dates) + "}", h, count=1)
p.write_text(h, encoding="utf-8")
