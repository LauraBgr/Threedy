"""Öffentliche Webseiten und Nachrichten der Wettbewerber abrufen und als Schnappschuss speichern.

- beachtet robots.txt, ruft langsam ab und nutzt nur Seiten ohne Login
- findet über die Sitemap passende Produkt- und Lösungsseiten
- speichert pro Seite Titel, Beschreibung, Überschriften, Buttons/Links (CTA-Kandidaten) und Fließtext
- erkennt über einen Fingerabdruck, ob sich eine Seite seit dem letzten Lauf geändert hat
"""
import datetime as dt
import hashlib
import json
import re
import time
import urllib.robotparser
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .pfade import DATEN, lies_json, schreib_json, slug

AGENT = "Mozilla/5.0 (compatible; PFH-Praxisprojekt-Wettbewerbsanalyse/0.1; Hochschulprojekt, nur oeffentliche Seiten)"
SITZUNG = requests.Session()
SITZUNG.headers.update({"User-Agent": AGENT, "Accept-Language": "en,de;q=0.8"})

_robots = {}
_letzter_abruf = {}


def darf_abrufen(url):
    teile = urlparse(url)
    basis = f"{teile.scheme}://{teile.netloc}"
    if basis not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = SITZUNG.get(basis + "/robots.txt", timeout=15)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except requests.RequestException:
            rp.parse([])
        _robots[basis] = rp
    return _robots[basis].can_fetch(AGENT, url)


def abrufen(url, pause=2.0):
    """Holt eine Seite höflich: robots.txt, Pause pro Website, Zeitlimit."""
    if not darf_abrufen(url):
        raise PermissionError("robots.txt verbietet den Abruf")
    host = urlparse(url).netloc
    warten = pause - (time.time() - _letzter_abruf.get(host, 0))
    if warten > 0:
        time.sleep(warten)
    _letzter_abruf[host] = time.time()
    r = SITZUNG.get(url, timeout=25)
    r.raise_for_status()
    return r


def _host(u):
    return urlparse(u).netloc.lower().removeprefix("www.") if hasattr(str, "removeprefix") else re.sub(r"^www\.", "", urlparse(u).netloc.lower())


def sitemap_eintraege(start, pause, max_sitemaps=12):
    """Alle URLs (mit lastmod) aus sitemap.xml und den in robots.txt genannten Sitemaps, auch verschachtelt."""
    try:   # Weiterleitungen folgen (z. B. threedy.io -> www.threedy.io)
        start = SITZUNG.head(start, allow_redirects=True, timeout=15).url or start
    except requests.RequestException:
        pass
    teile = urlparse(start)
    eintraege, zu_lesen, gelesen = {}, [f"{teile.scheme}://{teile.netloc}/sitemap.xml"], set()
    try:
        for zeile in SITZUNG.get(f"{teile.scheme}://{teile.netloc}/robots.txt", timeout=15).text.splitlines():
            if zeile.lower().startswith("sitemap:"):
                zu_lesen.insert(0, zeile.split(":", 1)[1].strip())
    except requests.RequestException:
        pass
    while zu_lesen and len(gelesen) < max_sitemaps and len(eintraege) < 5000:
        sm = zu_lesen.pop(0)
        if sm in gelesen:
            continue
        gelesen.add(sm)
        try:
            xml = ET.fromstring(abrufen(sm, pause).content)
        except Exception:
            continue
        for knoten in xml:
            loc = next((c.text.strip() for c in knoten if c.tag.endswith("loc") and c.text), "")
            lastmod = next((c.text.strip()[:10] for c in knoten if c.tag.endswith("lastmod") and c.text), "")
            if not loc:
                continue
            if knoten.tag.endswith("sitemap") or loc.endswith(".xml"):
                zu_lesen.append(loc)
            elif _host(loc) == _host(start):
                eintraege.setdefault(loc, lastmod)
    return list(eintraege.items())


def seiten_aus_sitemap(start, stichworte, maximal, pause):
    """Produkt- und Lösungsseiten aus der Sitemap: passende Stichworte, kurze Pfade (Übersichtsseiten) zuerst."""
    sperr = re.compile(r"/(blog|news|press|career|jobs|event|webinar|tag|author|legal|privacy|imprint|impressum)", re.I)
    passend = [u for u, _ in sitemap_eintraege(start, pause) if any(s in u.lower() for s in stichworte) and not sperr.search(u)]
    vorrang = re.compile(r"pric|preis|compar|vergleich|alternative", re.I)   # Preis- und Vergleichsseiten zuerst (Projektvorgabe)
    passend.sort(key=lambda u: (not vorrang.search(urlparse(u).path), urlparse(u).path.count("/"), len(u)))
    return passend[:maximal]


def seite_zerlegen(html, url):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "form"]):
        tag.decompose()
    meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    sprache = (soup.html.get("lang") if soup.html else "") or ""
    ueberschriften = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])]
    ueberschriften = [u for u in dict.fromkeys(ueberschriften) if 3 <= len(u) <= 160][:30]
    # CTA-Kandidaten: Buttons und kurze, auffällige Links
    cta = []
    for el in soup.find_all(["a", "button"]):
        t = el.get_text(" ", strip=True)
        cls = " ".join(el.get("class", [])).lower() if hasattr(el, "get") else ""
        if 3 <= len(t) <= 40 and (el.name == "button" or "btn" in cls or "button" in cls or "cta" in cls
                                  or re.search(r"demo|trial|contact|kontakt|test|start|get started|request|anfrage|download|talk|book|buy|pricing|preise", t, re.I)):
            cta.append(t)
    for nav in soup(["nav", "header", "footer"]):
        nav.decompose()
    haupt = soup.find("main") or soup.body or soup
    text = re.sub(r"\s+", " ", haupt.get_text(" ", strip=True))
    return {
        "titel": (soup.title.get_text(strip=True) if soup.title else "")[:200],
        "beschreibung": (meta.get("content", "") if meta else "")[:400],
        "sprache": sprache[:10],
        "ueberschriften": ueberschriften,
        "cta_kandidaten": list(dict.fromkeys(cta))[:25],
        "text": text[:20000],
    }


def aufraeumen(stand, behalten=8):
    """Pro Seite nur die letzten Schnappschüsse behalten, damit das Repository klein bleibt."""
    aktuell = {v["datei"] for v in stand.values()}
    ordner = DATEN / "schnappschuesse"
    if not ordner.exists():
        return
    gruppen = {}
    for f in ordner.rglob("*.json"):
        gruppen.setdefault(f.parent / f.name.split("__")[0], []).append(f)
    for dateien in gruppen.values():
        for alt in sorted(dateien)[:-behalten]:
            if str(alt.relative_to(DATEN)) not in aktuell:
                alt.unlink()


def sammeln(cfg, protokoll=print):
    e = cfg["einstellungen"]
    heute = dt.date.today().isoformat()
    stand = lies_json(DATEN / "stand.json", {})   # url -> {fingerabdruck, datum, datei}
    fehler, aenderungen, seiten_gesamt = [], [], 0
    for w in cfg["wettbewerber"]:
        name = w["name"]
        protokoll(f"– {name}")
        ziele = [{"url": w["start"], "region": w["region"]}] if w.get("start") else []   # ohne Website: nur News
        for s in w.get("seiten", []) or []:
            ziele.append({"url": s["url"], "region": s.get("region", w["region"])})
        if w.get("sitemap"):
            try:
                for u in seiten_aus_sitemap(w["start"], e["seiten_stichworte"], e["max_seiten_pro_firma"], e["pause_sekunden"]):
                    if u not in [z["url"] for z in ziele]:
                        ziele.append({"url": u, "region": w["region"]})
            except Exception as ex:
                fehler.append({"firma": name, "url": w["start"], "fehler": f"Sitemap: {ex}"})
        for z in ziele[: e["max_seiten_pro_firma"]]:
            url = z["url"]
            try:
                r = abrufen(url, e["pause_sekunden"])
                inhalt = seite_zerlegen(r.text, url)
                if len(inhalt["text"]) < 200:
                    raise ValueError("kaum Text auf der Seite (evtl. nur per JavaScript geladen)")
            except Exception as ex:
                fehler.append({"firma": name, "url": url, "fehler": str(ex)[:200]})
                protokoll(f"   ! {url}: {str(ex)[:120]}")
                continue
            # Fingerabdruck aus Titel, Beschreibung, Überschriften und Buttons: wechselnde Kleinigkeiten im Text zählen nicht als Änderung
            fp = hashlib.sha256("|".join([inhalt["titel"], inhalt["beschreibung"], *inhalt["ueberschriften"], *sorted(inhalt["cta_kandidaten"])]).encode()).hexdigest()[:16]
            ordner = DATEN / "schnappschuesse" / slug(name)
            datei = ordner / f"{slug(url)}__{heute}.json"
            alt = stand.get(url)
            schreib_json(datei, {"firma": name, "region": z["region"], "url": url, "datum": heute, "fingerabdruck": fp, **inhalt})
            if alt is None:
                aenderungen.append({"firma": name, "url": url, "art": "neu erfasst"})
            elif alt["fingerabdruck"] != fp:
                aenderungen.append({"firma": name, "url": url, "art": "geändert", "vorher": alt["datei"]})
            stand[url] = {"fingerabdruck": fp, "datum": heute, "datei": str(datei.relative_to(DATEN)), "firma": name, "region": z["region"]}
            seiten_gesamt += 1
            protokoll(f"   ✓ {url} ({len(inhalt['text'])} Zeichen)")
    protokoll("– Nachrichten und Pressemeldungen")
    from . import news
    fehler += news.sammeln(cfg, protokoll)
    schreib_json(DATEN / "stand.json", stand)
    aufraeumen(stand, behalten=e.get("schnappschuesse_behalten", 8))
    lauf = {"datum": heute, "seiten": seiten_gesamt, "fehler": fehler, "aenderungen": aenderungen}
    schreib_json(DATEN / "letzter_lauf.json", lauf)
    return lauf
