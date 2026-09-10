# Deployment

## 1. Git-Repo

Liegt öffentlich unter **https://github.com/DrdotHouse2106/ERPNext_Versand_Integration**
(Branch `main`). Updates:

```bash
cd /Users/marcelulber/Programmierung/ERPNext_Versand_Integration
git add -A && git commit -m "..." && git push
```

> `.secrets/` und die `Info*/`-Doku-Ordner sind per `.gitignore` ausgeschlossen.
> Da das Repo **öffentlich** ist: keine echten Keys in getrackte Dateien schreiben –
> Zugangsdaten gehören in **DHL Settings** (verschlüsselt in der DB).

---

## 2. Frappe Cloud – als Private App einbinden

1. Frappe-Cloud-Konto → **Bench Group** deiner Site (oder neue Group).
2. **Apps → Add App → From GitHub** (bzw. „Add your own app").
3. Frappe Cloud fragt nach der GitHub-Installation → Zugriff auf
   `DrdotHouse2106/ERPNext_Versand_Integration` erlauben.
4. Branch `main` wählen. Frappe Cloud liest `pyproject.toml`
   (App-Name `versand_integration`, benötigt `frappe`, `erpnext`).
5. **Add** → die App erscheint in der Bench Group.
6. **Deploy** der Bench Group (baut ein neues Image).
7. Nach dem Deploy: **Site → Apps → Install** `versand_integration`.
8. Bei Code-Updates: Commit + Push nach `main` → in Frappe Cloud
   **Update available** → **Deploy**.

Die `after_migrate`-Hook legt die Custom Fields am Lieferschein und die
Settings-Singletons (DHL / DPD / Deutsche Post) bei jedem Deploy/Migrate an.

Die Python-Abhängigkeit **`zeep`** (SOAP-Client für DPD) steht in `pyproject.toml`
und wird von Frappe Cloud beim Image-Build automatisch mitinstalliert. Self-hosted:
`bench pip install zeep` bzw. `bench setup requirements`.

---

## 3. Nach der Installation

1. Desk → **DHL Settings** (und bei Bedarf **DPD Settings** / **Deutsche Post Settings**)
   → Umgebung *Sandbox*, Zugangsdaten + Absenderadresse.
2. **Verbindung testen**.
3. Einen gebuchten **Lieferschein** öffnen → **Versand → Versandetikett erstellen**
   → Carrier wählen.

> **DPD**: nur DELIS-ID + Passwort nötig, `sendingDepot` kommt aus dem Login.
> **Deutsche Post**: BETA. Kein Testaccount – Modus auf *Vorschau* lassen
> (`retrievePreviewVoucherPDF`, kostenlos, Muster-PDF). Erst auf *Produktiv*
> stellen, wenn echte Marken (mit Portokasse-Abzug) gedruckt werden sollen.

---

## 4. Wechsel auf Produktion

1. DHL: Produktions-App im Developer Portal beantragen, Freischaltung der
   „Parcel DE Shipping"-API für die echte Abrechnungsnummer.
2. **DHL Settings**:
   * `Umgebung` = *Production*
   * `API Key` / `API Secret` der Produktions-App
   * `GKP Benutzername` / `GKP Passwort` (echter Geschäftskundenportal-Zugang)
   * `Abrechnungsnummer` = echte 14-stellige Nummer
   * `Nur validieren` = aus
3. Erneut **Verbindung testen**, dann eine echte Testsendung erzeugen und
   das Etikett prüfen.
