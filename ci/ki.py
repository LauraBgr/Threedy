"""Zugang zur KI über eine OpenAI-kompatible Schnittstelle (GWDG, später beliebig austauschbar).

Einstellungen über Umgebungsvariablen (lokal in .env, auf GitHub als Secrets):
  KI_BASIS_URL   z. B. https://chat-ai.academiccloud.de/v1   (GWDG SAIA)
  KI_SCHLUESSEL  API-Schlüssel
  KI_MODELL      Modellname, z. B. aus `python -m ci modelle`
Fehlt KI_SCHLUESSEL, läuft der Ersatzmodus ohne KI (einfache Stichwort-Auswertung).
"""
import json
import os
import re
import time

import requests


def konfiguration():
    return {
        # Leere Werte (z. B. nicht gesetzte GitHub-Secrets) zählen wie fehlende
        "basis": (os.environ.get("KI_BASIS_URL") or "https://chat-ai.academiccloud.de/v1").rstrip("/"),
        "schluessel": (os.environ.get("KI_SCHLUESSEL") or "").strip(),
        "modell": (os.environ.get("KI_MODELL") or "meta-llama-3.1-8b-instruct").strip(),
    }


def verfuegbar():
    return bool(konfiguration()["schluessel"])


def modelle():
    k = konfiguration()
    r = requests.get(f"{k['basis']}/models", headers={"Authorization": f"Bearer {k['schluessel']}"}, timeout=30)
    r.raise_for_status()
    return [m.get("id") for m in r.json().get("data", [])]


def fragen(prompt, json_antwort=True, versuche=3):
    """Schickt einen Prompt an die KI. Bei json_antwort wird die Antwort als JSON geparst."""
    k = konfiguration()
    letzter = None
    for i in range(versuche):
        try:
            r = requests.post(f"{k['basis']}/chat/completions", timeout=180,
                              headers={"Authorization": f"Bearer {k['schluessel']}", "Content-Type": "application/json"},
                              json={"model": k["modell"], "temperature": 0.1,
                                    "messages": [{"role": "user", "content": prompt}]})
            if r.status_code == 429:          # Ratenlimit: kurz warten
                time.sleep(20 * (i + 1)); continue
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
            if not json_antwort:
                return text.strip()
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
            return json.loads(text[text.find("{"): text.rfind("}") + 1])
        except Exception as ex:
            letzter = ex
            time.sleep(3)
    raise RuntimeError(f"KI-Anfrage fehlgeschlagen: {letzter}")
