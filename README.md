# ERPNext Versand Integration

Frappe-/ERPNext-App zur Erzeugung von **Versandetiketten direkt über die Carrier-APIs** –
ohne Drittanbieter-Middleware.

| Carrier | API | Stand |
| --- | --- | --- |
| **DHL** | Parcel DE Shipping v2 (REST, OAuth2/Basic) | implementiert, gegen Sandbox testbar |
| **DPD** | DE WebConnect (SOAP: LoginService V2.0 + ShipmentService V4.5, via `zeep`) | implementiert, gegen Stage testbar – SOAP-Header/Response noch nicht live verifiziert |
| **Deutsche Post** | Internetmarke OneClickForApp (1C4A) V3 (SOAP) | **BETA**, mangels Zugangsdaten noch nicht getestet |

Geschrieben für **Frappe / ERPNext v15–v16**. Python-Abhängigkeit: `zeep` (SOAP, für DPD).

> **Repo** heißt `ERPNext_Versand_Integration`, die **Frappe-App** heißt
> `versand_integration` (Python-Modulname). Frappe Cloud / `bench` lesen den
> App-Namen aus `pyproject.toml` – der Repo-Name muss nicht übereinstimmen.

---

## Was die App macht

| Objekt | Zweck |
| --- | --- |
| **DHL Settings** / **DPD Settings** / **Deutsche Post Settings** (je Single) | Zugangsdaten, Absenderadresse, Voreinstellungen, „Verbindung testen" |
| **Versandsendung** (submittable) | Eine Sendung zu einem Lieferschein: Carrier, Empfänger, Gewicht/Maße, Services, Mehrcolli, Etikett-PDF, Sendungsnummer, Tracking-Link, API-Protokoll |
| **Versandsendung Paket** (Child) | Einzelne Colli bei Mehrpaketsendungen (DHL/DPD) |
| Button **„Versandetikett erstellen"** im *Lieferschein* | Carrier wählen → Versandsendung anlegen, API rufen, PDF anhängen & öffnen |
| Custom Fields am *Lieferschein* | `Versandsendung`, `Sendungsnummer`, `Sendungsverfolgung` |

Ablauf: **Lieferschein buchen → „Versandetikett erstellen" → Carrier wählen** →
PDF öffnet sich, Sendungsnummer & Tracking-Link stehen am Lieferschein und an der
Versandsendung. Storno der Versandsendung:
* DHL – Sendung wird per `DELETE /orders` gelöscht.
* DPD – nicht nötig (nicht manifestierte Sendungen einfach nicht abschließen).
* Deutsche Post – Erstattung läuft über den separaten Dienst 1C4Refund (nicht in dieser App).

---

## Installation

### Frappe Cloud (Private App)

Siehe [DEPLOYMENT.md](DEPLOYMENT.md).

### Self-hosted Bench

```bash
cd ~/frappe-bench
bench get-app versand_integration https://github.com/DrdotHouse2106/ERPNext_Versand_Integration.git
bench --site <site> install-app versand_integration
bench --site <site> migrate
bench build --app versand_integration
```

---

## Konfiguration

1. **Desk → „DHL Settings"** öffnen.
2. `Umgebung` = *Sandbox* zum Testen.
3. `Authentifizierung`:
   * **OAuth2** (empfohlen, wie die offizielle DHL-Onboarding-Collection) –
     *API Key* + *API Secret* + GKP-Login. Token wird gecacht.
     Sandbox-Login, wenn leer: `user-valid` / `SandboxPasswort2023!`.
   * **Basic** – *API Key* (als Header) + GKP-Login.
     Sandbox-Login, wenn leer: `sandy_sandbox` / `pass`.
4. `API Key` / `API Secret` aus dem [DHL Developer Portal](https://developer.dhl.com/).
5. **Absender / Retourenadresse** ausfüllen (Pflicht: Name 1, PLZ, Ort).
6. In Produktion: `Abrechnungsnummer` (14-stellig) eintragen. In der Sandbox
   werden je Produkt die offiziellen Test-Abrechnungsnummern verwendet.
7. **„Verbindung testen"** klicken → macht einen `validate=true`-Aufruf.

### Testzugangsdaten schnell laden (nur self-hosted)

Format siehe [dhl_credentials.example.json](dhl_credentials.example.json). Lege eine
lokale, **nicht** versionierte `.secrets/dhl_credentials.json` an (alles unter
`.secrets/` ist gitignored) und lade sie:

```bash
./scripts/load_test_credentials.sh <site-name>
# bzw.
bench --site <site> execute versand_integration.utils.credentials.load_from_file
```

---

## DHL-Sandbox – wichtige Werte

| | Wert |
| --- | --- |
| Basis-URL | `https://api-sandbox.dhl.com/parcel/de/shipping/v2` |
| Token-URL (OAuth2) | `https://api-sandbox.dhl.com/parcel/de/account/auth/ropc/v1/token` |
| OAuth2-Testlogin | `user-valid` / `SandboxPasswort2023!` (+ dein API Key/Secret als client_id/secret) |
| Basic-Auth-Testlogin | `sandy_sandbox` / `pass` (+ API Key als `dhl-api-key`-Header) |
| Abrechnungsnr. `V01PAK` | `33333333330102` (mit Services), `…0101` (ohne) |
| Profil | `STANDARD_GRUPPENPROFIL` |
| Druckformat | `910-300-700` (A4) |

Leere Felder für GKP-Benutzer/Passwort und Abrechnungsnummer werden in der
Sandbox automatisch mit den obigen Testwerten belegt (je nach `auth_method`).

Produkte: `V01PAK` (DHL Paket), `V53WPAK` (Paket International), `V54EPAK`
(Europaket), `V62KP` (DHL Kleinpaket), `V62WP` (Warenpost, Altname),
`V66WPI` (Warenpost International).

> Herstellerdoku (DHL-OpenAPI-Spec, DPD-WSDL/PDFs, Internetmarke-WSDL) wird lokal
> unter `Info DHL Paket/`, `Info DPD/`, `Infos Porto/` gehalten – gitignored.

---

## DPD (Stage)

| | Wert |
| --- | --- |
| Login-WSDL | `https://public-ws-stage.dpd.com/services/LoginService/V2_0/?wsdl` |
| Shipment-WSDL | `https://public-ws-stage.dpd.com/services/ShipmentService/V4_5/?wsdl` |
| Testzugang | DELIS-ID `sandboxdpd` / Passwort `xMmshh1` |
| `sendingDepot` | kommt aus `getAuth` (nicht selbst setzen) |
| Gewicht | Gramm auf 10 g gerundet (`300` = 3 kg) – die App rechnet aus kg um |

Produkte: `CL` (Classic), `E12/E18/E830` (Express), `IE2` (Int. Express),
`PSD`/`CL2SHOP`/`SHOP2SHOP` (Shop), `MAIL`.

## Deutsche Post / Internetmarke (1C4A V3) — BETA

Braucht einen **Partnervertrag** (`PARTNER_ID`, `SCHLUESSEL`, `KEY_PHASE`) **und**
ein **Portokasse-Konto** (E-Mail + Passwort). Es gibt keine Sandbox – Tests laufen
gegen Produktion mit Kleinstbeträgen. Signatur: `SHA-512` über
`PARTNER_ID::TIMESTAMP::KEY_PHASE::SCHLUESSEL` (Whitespace entfernt).
Der Frankierbetrag (Cent) muss pro Sendung oder als Default gesetzt sein.

---

## Architektur

```
versand_integration/
├── carriers/
│   ├── base.py          # BaseCarrier, LabelResult, LabelPackage (normalisiert)
│   ├── registry.py      # Carrier-Name -> Klasse
│   ├── exceptions.py    # CarrierError / CarrierConfigError / CarrierAPIError
│   ├── dhl/             # Parcel DE Shipping v2 (REST): constants, client, mapper, carrier
│   ├── dpd/             # DE WebConnect (SOAP via zeep): constants, client, mapper, carrier
│   └── deutsche_post/   # Internetmarke 1C4A V3 (SOAP): constants, signature, client, mapper, carrier
├── api.py               # whitelisted: create_shipment_from_delivery_note(carrier=…)
├── setup/install.py     # Custom Fields, Settings-Singletons
├── utils/credentials.py # .secrets/*.json -> Settings (nur self-hosted, zum Testen)
└── versand_integration/doctype/…   # DHL/DPD/Deutsche Post Settings, Versandsendung(+Paket)
```

Ein neuer Carrier = neuer Ordner `carriers/<name>/` mit einer `BaseCarrier`-Klasse,
die `LabelResult` zurückgibt, plus Eintrag in `registry.py` und ein Settings-Doctype.

---

## Sicherheit

* Zugangsdaten liegen als `Password`-Felder verschlüsselt in der DB.
* `.secrets/` ist per `.gitignore` ausgeschlossen – **niemals** echte Keys committen.
* Alle API-Aufrufe laufen server-seitig; die whitelisted-Methoden prüfen
  `Delivery Note`-Leserechte.

## Lizenz

MIT
