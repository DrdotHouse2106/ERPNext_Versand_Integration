# Versand Integration

Frappe-/ERPNext-App zur Erzeugung von **Versandetiketten direkt über die Carrier-APIs** –
ohne Drittanbieter-Middleware.

* **DHL Parcel DE Shipping API v2** – vollständig implementiert (Etikett erstellen,
  stornieren, Sandbox + Produktion, OAuth2 **oder** Basic Auth).
* **DPD** und **Deutsche Post / Portokasse (Internetmarke)** – Architektur vorbereitet
  (`versand_integration/carriers/…`), noch nicht implementiert.

Getestet für **Frappe / ERPNext v15–v16**.

---

## Was die App macht

| Objekt | Zweck |
| --- | --- |
| **DHL Settings** (Single) | Zugangsdaten, Absenderadresse, Etiketten-Voreinstellungen, „Verbindung testen" |
| **Versandsendung** (submittable) | Eine Sendung zu einem Lieferschein: Empfänger, Gewicht/Maße, Services, Mehrcolli, Etikett-PDF, Sendungsnummer, Tracking-Link |
| **Versandsendung Paket** (Child) | Einzelne Colli bei Mehrpaketsendungen |
| Button **„Versandetikett erstellen"** im *Lieferschein* | Legt Versandsendung an, ruft die DHL-API, hängt das PDF an, öffnet es |
| Custom Fields am *Lieferschein* | `Versandsendung`, `Sendungsnummer`, `Sendungsverfolgung` |

Ablauf: **Lieferschein buchen → „Versandetikett erstellen"** → PDF öffnet sich,
Sendungsnummer & Tracking-Link stehen am Lieferschein und an der Versandsendung.
Wird die Versandsendung storniert, wird die Sendung auch bei DHL gelöscht (`DELETE /orders`).

---

## Installation

### Frappe Cloud (Private App)

Siehe [DEPLOYMENT.md](DEPLOYMENT.md).

### Self-hosted Bench

```bash
cd ~/frappe-bench
bench get-app versand_integration https://github.com/<user>/versand_integration.git
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

`.secrets/dhl_credentials.json` (nicht im Git) enthält ein Beispiel/Testprofil:

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

> API-Spezifikation und offizielle Postman-Onboarding-Collection liegen unter
> `Info DHL Paket/` (gitignored).

---

## Architektur

```
versand_integration/
├── carriers/
│   ├── base.py          # BaseCarrier, LabelResult, LabelPackage (normalisiert)
│   ├── registry.py      # Name -> Carrier-Klasse
│   ├── exceptions.py
│   └── dhl/
│       ├── constants.py # URLs, Sandbox-Werte, Produkte, Länder-Mapping
│       ├── client.py    # HTTP-Client (Auth, /orders POST/GET/DELETE, Token-Cache)
│       ├── mapper.py    # Versandsendung -> DHL-Payload
│       └── carrier.py   # DHLCarrier(BaseCarrier)
├── api.py               # whitelisted: create_shipment_from_delivery_note
├── setup/install.py     # Custom Fields, Singleton
└── versand_integration/doctype/…
```

Ein neuer Carrier = neue Klasse in `carriers/<name>/carrier.py`, die `BaseCarrier`
implementiert und `LabelResult` zurückgibt, plus Eintrag in `registry.py`.

---

## Sicherheit

* Zugangsdaten liegen als `Password`-Felder verschlüsselt in der DB.
* `.secrets/` ist per `.gitignore` ausgeschlossen – **niemals** echte Keys committen.
* Alle API-Aufrufe laufen server-seitig; die whitelisted-Methoden prüfen
  `Delivery Note`-Leserechte.

## Lizenz

MIT
