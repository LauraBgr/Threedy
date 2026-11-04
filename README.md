# Competitive Intelligence für Threedy

Prototyp aus dem PFH-Praxisprojekt (WiSe 2026/27). Er beobachtet, wie Wettbewerber von Threedy in Europa und den USA ihre Produkte darstellen, und zeigt das Ergebnis als Dashboard im Browser.

**Ablauf, jede Woche automatisch:**

1. **Sammeln:** öffentliche Webseiten (Startseite, Produkt- und Lösungsseiten über die Sitemap) und Nachrichten (Google News, EU und USA)
2. **Auswerten:** eine KI liest jede Seite mit einem festen Prompt (`prompts/seite_auswerten.md`) und liefert immer dasselbe Format: Botschaft, Keywords, Themen, Call to Action, Belege, Kunden, Branchen
3. **Vergleichen:** Was hat sich seit letzter Woche geändert? Wo hat Threedy Lücken?
4. **Zusammenfassen:** ein zweiter Prompt (`prompts/zusammenfassung.md`) schreibt eine kurze Einordnung
5. **Veröffentlichen:** `docs/index.html` wird neu gebaut und über GitHub Pages bereitgestellt

## Ordner

| Ordner | Inhalt |
|---|---|
| `config/wettbewerber.yaml` | **die Liste der Wettbewerber und Quellen**, das einzige, was man regelmäßig anpasst |
| `prompts/` | die beiden Prompts als Text, ändern ohne Programmieren |
| `ci/` | das Programm (Python) |
| `data/` | gesammelte Schnappschüsse, Auswertungen, Änderungsprotokoll |
| `docs/` | das fertige Dashboard |
| `.github/workflows/` | der automatische Wochenlauf |

## Lokal ausprobieren

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.beispiel .env          # GWDG-Schlüssel eintragen
.venv/bin/python -m ci modelle # zeigt, welche Modelle der Schlüssel nutzen darf
.venv/bin/python -m ci alles   # sammeln + auswerten + Dashboard bauen
open docs/index.html
```

Ohne Schlüssel läuft ein **Ersatzmodus**, der Keywords und Themen nur grob per Stichwortsuche bestimmt. So lässt sich alles testen, bevor die KI angeschlossen ist.

Einzelne Schritte: `python -m ci sammeln`, `python -m ci auswerten`, `python -m ci seite`.

## Einrichtung auf GitHub (einmalig)

1. Neues Repository anlegen (am besten gleich im GitHub-Konto von Threedy oder später dorthin übertragen) und diesen Ordner hochladen:
   ```bash
   git init && git add . && git commit -m "Prototyp"
   git branch -M main
   git remote add origin https://github.com/<konto>/<repo>.git
   git push -u origin main
   ```
2. **Settings → Secrets and variables → Actions → New repository secret**, drei Einträge:
   - `KI_BASIS_URL` = `https://chat-ai.academiccloud.de/v1` (GWDG)
   - `KI_SCHLUESSEL` = euer GWDG-API-Schlüssel
   - `KI_MODELL` = ein Modell aus `python -m ci modelle`
3. **Settings → Pages → Source: GitHub Actions**
4. **Actions → Wöchentliche Wettbewerbsanalyse → Run workflow**, für den ersten Lauf. Danach läuft er jeden Montag von allein.
5. Die Adresse des Dashboards steht danach unter Settings → Pages (z. B. `https://<konto>.github.io/<repo>/`).

Schlägt ein Lauf fehl, schickt GitHub automatisch eine Mail an die Besitzer des Repositorys.

## Regeln beim Sammeln

- nur öffentlich zugängliche Seiten, keine Logins
- `robots.txt` wird beachtet: gesperrte Seiten werden ausgelassen und unter „Quellen“ angezeigt
- höchstens eine Anfrage alle 2 Sekunden pro Website, eindeutige Kennung im User-Agent
- Anzeigen-Bibliotheken von LinkedIn und Google haben keine offene Schnittstelle und sind bewusst nicht automatisiert

Weitere Hinweise zur Pflege: [WARTUNG.md](WARTUNG.md)
