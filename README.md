# ERPNext Versand Integration

Frappe-/ERPNext-App zur Erzeugung von **Versandetiketten direkt über die Carrier-APIs** –
ohne Drittanbieter-Middleware.

| Carrier | API | Stand |
| --- | --- | --- |
| **DHL** | Parcel DE Shipping v2 (REST, OAuth2/Basic) | implementiert, gegen Sandbox testbar |
| **DPD** | DE WebConnect (SOAP: LoginService V2.0 + ShipmentService V4.5, via `zeep`) | implementiert, gegen Stage testbar – SOAP-Header/Response noch nicht live verifiziert |
| **Deutsche Post** | Internetmarke OneClickForApp (1C4A) V3 (SOAP) | **BETA** – Vorschau-Modus kostenlos testbar, Produktiv-Modus belastet die Portokasse |

Geschrieben für **Frappe / ERPNext v15–v16**. Python-Abhängigkeit: `zeep` (SOAP, für DPD).

> **Repo** heißt `ERPNext_Versand_Integration`, die **Frappe-App** heißt
> `versand_integration` (Python-Modulname). Frappe Cloud / `bench` lesen den
> App-Namen aus `pyproject.toml` – der Repo-Name muss nicht übereinstimmen.

---

## Was die App macht

| Objekt | Zweck |
| --- | --- |
| **DHL Settings** / **DPD Settings** / **Deutsche Post Settings** (je Single) | Zugangsdaten, Fallback-Absender, Voreinstellungen, „Verbindung testen" |
| **Versandabsender** | Marken-/Absenderprofil: Adresse, Retoure, Briefkopf, DHL-Abrechnungsnummern je Produkt |
| **Versandsendung** (submittable) | Eine Sendung zu einem Lieferschein: Carrier, Absender, Empfänger, Gewicht/Maße, Services, Mehrcolli, Etikett-PDF, Sendungsnummer, Tracking-Link, API-Protokoll |
| **Versandsendung Paket** (Child) | Einzelne Colli bei Mehrpaketsendungen (DHL/DPD) |
| Button **„Versandetikett erstellen"** im *Lieferschein* | Carrier wählen → Versandsendung anlegen, API rufen, PDF anhängen & öffnen |
| Custom Fields am *Lieferschein* | `Versandsendung`, `Sendungsnummer`, `Sendungsverfolgung` |

Ablauf: **Lieferschein buchen → „Versandetikett erstellen" → Carrier + Absender wählen** →
PDF öffnet sich, Sendungsnummer & Tracking-Link stehen am Lieferschein und an der
Versandsendung. Storno der Versandsendung:
* DHL – Sendung wird per `DELETE /orders` gelöscht.
* DPD – nicht nötig (nicht manifestierte Sendungen einfach nicht abschließen).
* Deutsche Post – Erstattung läuft über den separaten Dienst 1C4Refund (nicht in dieser App).

---

## Mehrere Marken / Absender (`Versandabsender`)

Eine ERPNext-Company, mehrere Marken (z. B. *FranceTec*, *Schmelzkammer*,
*kfz-isolierung.de*)? Pro Marke ein **Versandabsender**-Datensatz:

* Absender- und Retourenadresse, E-Mail/Telefon
* **Briefkopf** (Letter Head) → landet automatisch auf Auftrag/Lieferschein/Rechnung,
  solange dort noch keiner gesetzt ist (unterschiedliche Logos je Marke)
* DHL/DPD-Overrides **nur falls nötig** – siehe Abrechnungsnummern unten

### DHL-Abrechnungsnummern

Gleiche EKP, je Produkt eine eigene 14-stellige Nummer (Stelle 11–12 = Produktnummer):
in den **DHL Settings → „Abrechnungsnummern je Produkt"** einmal global eintragen.
Nur wenn eine Marke einen komplett eigenen DHL-Vertrag hat, im jeweiligen
Versandabsender die abweichenden Nummern als **Override** setzen. Reihenfolge:
Versandabsender-Override → DHL-Settings-Tabelle → einfaches Fallback-Feld → (Sandbox) Testnummer.

**Zuordnung** je Lieferschein (Feld *Versandabsender / Marke*):
Kunde → Auftrag → Lieferschein (wird durchgereicht), sonst der als *Standard*
markierte Versandabsender, sonst die Absenderfelder im Carrier-Settings-Doctype.
Beim „Versandetikett erstellen" lässt sich der Absender im Dialog noch überschreiben.

Logo-Wechsel auf Dokumenten = **Letter Head** je Marke anlegen und im Versandabsender
verknüpfen. Kein Company-Wechsel nötig.

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
5. **Absender / Retourenadresse** als Fallback ausfüllen – oder besser gleich
   **`Versandabsender`**-Datensätze anlegen (siehe oben) und die Abrechnungsnummern
   dort je Produkt pflegen.
6. In der Sandbox werden je Produkt die offiziellen Test-Abrechnungsnummern
   verwendet, wenn keine hinterlegt ist.
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

In den Auswahlfeldern stehen lesbare Namen; die App übersetzt sie in die
DHL-Codes: DHL Paket (national) = `V01PAK`, DHL Paket International = `V53WPAK`,
DHL Europaket = `V54EPAK`, DHL Kleinpaket = `V62KP`, Warenpost = `V62WP`,
Warenpost International = `V66WPI`. Jedes Produkt braucht eine dazu passende
Abrechnungsnummer (Stelle 11–12 = Produktnummer).

**Zusatzleistungen (VAS):** je Sendung ankreuzbar – u. a. **Premium**
(bevorzugte Behandlung, v. a. Ausland) und **GoGreen Plus** (klimafreundlich).
In den DHL Settings als Standard setzbar: „Premium bei Auslandssendungen"
(greift automatisch bei V53WPAK/V54EPAK/V66WPI) und „GoGreen Plus immer aktiv".

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
ein **Portokasse-Konto** (E-Mail + Passwort). Signatur: `SHA-512` über
`PARTNER_ID::TIMESTAMP::KEY_PHASE::SCHLUESSEL` (Whitespace entfernt).

**Es gibt keinen Testaccount.** Deshalb hat das Feld `Modus` zwei Stufen:

| Modus | Aufruf | Kosten |
| --- | --- | --- |
| **Vorschau** (Default) | `retrievePreviewVoucherPDF` | **0 € – kein Portokasse-Abzug.** PDF ist ein als Muster gekennzeichnetes, **nicht versandfähiges** Voucher. Testet Signatur, Produktcode, Layout, Seitenformat, PDF-Handling. |
| **Produktiv** | `checkoutShoppingCartPDF` | echte Marke, Portokasse wird belastet (Standardbrief ~0,95 €). Nicht genutzte Marken sind über **1C4Refund** erstattbar (separater Dienst, hier nicht implementiert). |

„Verbindung testen" ist kostenlos: `retrievePageFormats` (prüft Partner-Signatur)
+ `authenticateUser` (prüft Portokasse-Login, zeigt Guthaben).

Der Frankierbetrag (Cent) ist nur im Produktiv-Modus nötig – pro Sendung
(`Frankierbetrag (Cent)`) oder als Default in den Settings.

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
├── absender.py          # Versandabsender/Marke -> ResolvedAbsender (Adresse, DHL-Abr.-Nr.)
├── api.py               # whitelisted: create_shipment_from_delivery_note(carrier, versandabsender)
├── setup/install.py     # Custom Fields (inkl. vi_versandabsender), Settings-Singletons
├── setup/letter_head.py # Briefkopf aus Versandabsender auf SO/DN/SI
├── utils/credentials.py # .secrets/*.json -> Settings (nur self-hosted, zum Testen)
└── versand_integration/doctype/…   # Settings (DHL/DPD/DP), Versandabsender(+DHL-Abr.-Nr.), Versandsendung(+Paket)
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
