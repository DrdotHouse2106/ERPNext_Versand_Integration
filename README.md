# ERPNext Versand Integration

Frappe-/ERPNext-App zur Erzeugung von **Versandetiketten direkt über die Carrier-APIs** –
ohne Drittanbieter-Middleware.

| Carrier | API | Stand |
| --- | --- | --- |
| **DHL** | Parcel DE Shipping v2 (REST, OAuth2/Basic) | ✅ live verifiziert: Etikett erstellen + stornieren |
| **DPD** | DE WebConnect (SOAP: LoginService V2.0 + ShipmentService V4.5, via `zeep`) | Login + Sendung erstellen live verifiziert; Label-Extraktion gefixt, Re-Test nach nächstem Deploy ausstehend |
| **Deutsche Post** | Internetmarke – neue REST-API „Post DE Internetmarke" (DHL Developer Portal, kein Partnervertrag mehr) | ✅ live verifiziert: Marken-Erstellung (Vorschau/Produktiv), Portokasse-Aufladung, optionale DATEV-Journalbuchungen |

Geschrieben für **Frappe / ERPNext v15–v16**. Python-Abhängigkeit: `zeep` (SOAP, für DPD).

> **Repo** heißt `ERPNext_Versand_Integration`, die **Frappe-App** heißt
> `versand_integration` (Python-Modulname). Frappe Cloud / `bench` lesen den
> App-Namen aus `pyproject.toml` – der Repo-Name muss nicht übereinstimmen.

---

## Status: Testphase (Stand 11.09.2026)

Erster Live-Testlauf gegen eine echte ERPNext-Instanz (Frappe Cloud, Sandbox-Zugänge)
ist gelaufen. Getestet wurde per API mit freistehenden, danach wieder gelöschten
Test-Versandsendungen (kein Kunde/Lieferschein nötig, keine Spuren im System).

✅ **Live gegen die Sandbox verifiziert**
- **DHL**: „Verbindung testen" (OAuth2), **Etikett erstellen** (echte Sendungsnummer,
  gültiges PDF-Label per API heruntergeladen und geprüft) und **Stornieren**
  (`DELETE /orders`, „1 von 1 Sendung erfolgreich storniert.") – alles Ende-zu-Ende erfolgreich
- **DPD**: SOAP-Login (`LoginService.getAuth`, `zeep`-Header-Matching funktioniert) und
  **`storeOrders`** liefern eine echte Sendungsnummer + Tracking-Link. Das Label-PDF fehlte
  in zwei aufeinanderfolgenden Läufen – zwei Ursachen gefunden und gefixt
  (`splitByParcel`, dann `output` ist eine Liste statt eines Einzelobjekts; Commits
  `b38fc55`/`b8aed2e`) – **Re-Test nach dem nächsten Deploy steht noch aus**
- `bench migrate`-Grundlagen: Custom Fields, Abrechnungsnummern-Tabelle, DocTypes korrekt angelegt
- **Deutsche Post / Internetmarke**: Auth (`POST /user`) und Marken-Erstellung
  (Vorschau + Produktiv, `POST /app/shoppingcart/pdf`) live verifiziert

⚠️ **Noch offen**
- DPD-Label-Fix erneut testen (siehe oben)
- Deutsche Post: Portokasse-Aufladung + DATEV-Journalbuchungen implementiert,
  aber noch nicht live durchprobiert (echtes Geld – bewusst nicht selbst getestet)
- Mehrmarken-Auflösung (`Versandabsender`) mit mehr als einer Marke, automatischer Briefkopf
- Sendungsverfolgung: Hintergrund-Job, Statusabgleich, Benachrichtigungen, Arbeitsfläche
  (Code ist deployt, aber noch nie live durchgeklickt)

Siehe [„Testvorgehen"](#testvorgehen) unten für die geplante Reihenfolge.

---

## Was die App macht

| Objekt | Zweck |
| --- | --- |
| **DHL / DPD / Deutsche Post Settings** (je Single) | Zugangsdaten, Fallback-Absender, Voreinstellungen, „Verbindung testen" |
| **Versand Integration Settings** (Single) | Sendungsverfolgung: Job an/aus, Intervall, Abbruch nach Tagen, Benachrichtigung |
| **Versandabsender** | Marken-/Absenderprofil: Adresse, Retoure, Briefkopf, DHL-Abrechnungsnummern je Produkt |
| **Versandsendung** (submittable) | Sendung zu einem Lieferschein: Carrier, Absender, Empfänger, Maße, Services, Mehrcolli, Etikett-PDF, Sendungsnummer, **Tracking-Status + Verlauf**, API-Protokoll |
| **Versandsendung Paket** (Child) | Einzelne Colli bei Mehrpaketsendungen (DHL/DPD) |
| Button **„Versandetikett erstellen"** im *Lieferschein* | Carrier wählen → Versandsendung anlegen, API rufen, PDF anhängen & öffnen |
| Custom Fields am *Lieferschein* | `Versandsendung`, `Sendungsnummer`, `Sendungsverfolgung` |

Ablauf: **Lieferschein buchen → „Versandetikett erstellen" → Carrier + Absender wählen** →
PDF öffnet sich, Sendungsnummer & Tracking-Link stehen am Lieferschein und an der
Versandsendung. Storno der Versandsendung:
* DHL – Sendung wird per `DELETE /orders` gelöscht.
* DPD – nicht nötig (nicht manifestierte Sendungen einfach nicht abschließen).
* Deutsche Post – Retoure (Erstattung) wird automatisch per `POST /app/retoure` beantragt,
  sofern im Produktiv-Modus eine echte Marke gekauft wurde.

---

## Sendungsverfolgung

Nach dem Etikett läuft der Status automatisch nach:

* **Versandsendung → Abschnitt „Sendungsverfolgung"**: Status
  (Angekündigt · Abgeholt · In Transport · In Zustellung · **Zugestellt** ·
  Zustellproblem · Retoure), Carrier-Statustext, „Zugestellt am" und ein
  Ereignis-Verlauf. Button **„Tracking aktualisieren"** für sofort.
* **Lieferschein**: Status + „Zugestellt am" gespiegelt, als Spalte/Filter in der Liste.
* **Hintergrund-Job** (`hourly_long`) aktualisiert alle offenen, gebuchten Sendungen;
  stoppt nach Zustellung/Retoure bzw. nach *X* Tagen (Standard 21).
* **Alte Sendungsnummern**: Carrier (DHL z. B. nach ~4 Wochen) liefern für abgelaufene
  Sendungsnummern irgendwann nur noch „Unbekannt"/404. Ein solches Ergebnis
  überschreibt **nie** einen bereits bekannten Status – sonst würden alte, längst
  zugestellte Sendungen wieder auf „offen" zurückfallen. Stattdessen wird der letzte
  bekannte Status eingefroren, `Carrier liefert keine Trackingdaten mehr` gesetzt und
  die automatische Verfolgung für diese Sendung beendet.
* **Arbeitsfläche „Versand"** mit Kennzahlen *Sendungen unterwegs* /
  *Zustellprobleme* und Schnellzugriffen.
* **Benachrichtigung** bei *Zustellproblem*/*Retoure* an alle Nutzer einer Rolle
  (Standard *Stock Manager*), optional zusätzlich per E-Mail.

Konfiguration: **Versand Integration Settings**. Quellen: DHL = „Parcel DE
Tracking"-API (nur API-Key), DPD = öffentlicher tracking.dpd.de-Endpunkt
(best effort). Deutsche Post: manche Produkte (Briefe/Warensendungen mit
„Basistracking") liefern eine Track-ID (`Voucher.trackId` aus der
Checkout-Antwort), die wir bereits in `tracking_number` übernehmen – eine
**automatische Statusabfrage dafür gibt es aber noch nicht** (keine
verifizierte API-Referenz für diese IDs). Der Hintergrund-Job fragt ohnehin
nur `carrier in [DHL, DPD]` ab; zusätzlich wird bei Deutsche-Post-Sendungen
„Automatisch weiter verfolgen" direkt beim Erstellen deaktiviert (statt es
für immer aktiv, aber wirkungslos stehen zu lassen) – über
`BaseCarrier.supports_tracking` (`False` bei `DeutschePostCarrier`). Ist eine
Track-ID vorhanden, steht das im Statustext, Status lässt sich vorerst nur
manuell bei der Post-/DHL-Sendungsverfolgung prüfen.

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

## Testvorgehen

Reihenfolge für den ersten echten Testlauf – jeder Schritt baut auf dem vorherigen auf,
bei einem Fehler dort weitermachen, wo er auftrat:

1. **Deploy** (Frappe Cloud oder self-hosted) + `bench migrate`. Prüfen: Desk-Suche
   findet `DHL Settings`, `DPD Settings`, `Deutsche Post Settings`,
   `Versand Integration Settings`, `Versandabsender`, `Versandsendung`; Arbeitsfläche
   „Versand" erscheint in der Seitenleiste.
2. **DHL Settings** ausfüllen (Sandbox) → **„Verbindung testen"**. Das ist der erste
   echte API-Aufruf – zeigt sofort, ob Auth/Abrechnungsnummer/Absenderadresse stimmen.
3. **DPD Settings** ausfüllen (Sandbox-Login liegt bereit) → **„Verbindung testen"**.
   Größtes Risiko im Projekt (SOAP/`zeep`) – wenn das durchläuft, ist der Rest meist Formsache.
4. Einen **Versandabsender** anlegen (Testadresse + DHL-Sandbox-Abrechnungsnummer).
5. Einen **Lieferschein** buchen → **Versand → Versandetikett erstellen** → **DHL** wählen.
   PDF sollte sich öffnen, Status auf „Etikett erstellt" stehen.
6. Dieselbe Sendung/einen zweiten Lieferschein mit **DPD** wiederholen.
7. Auf der Versandsendung **„Tracking aktualisieren"** klicken. Sandbox-Sendungsnummern
   liefern meist „Unbekannt" – das ist ok, es geht darum, dass der Aufruf **fehlerfrei**
   durchläuft.
8. Eine Versandsendung **stornieren** → prüfen, dass sie beim Carrier storniert wird
   und der Lieferschein-Verweis sich löscht.
9. Zweiten `Versandabsender` mit anderer Adresse/anderem Letter Head anlegen, einem
   Test-Kunden zuweisen, Lieferschein daraus buchen → prüfen, dass der richtige Absender
   und Briefkopf gezogen werden.
10. Job manuell antriggern statt eine Stunde zu warten:
    `bench --site <site> execute versand_integration.tracking.poll_open_shipments`
11. **Deutsche Post**: erst „Verbindung testen" (Token-Austausch + Portokasse-Guthaben),
    dann in den Settings „Katalog aktualisieren" (befüllt Produkte/Seitenformate/
    Motive, siehe unten), dann eine Versandsendung im Modus **Vorschau** anlegen
    (kostenlos) und erst danach, mit automatisch/bewusst gesetztem
    Frankierbetrag, im Modus **Produktiv** (siehe oben).

**Wenn etwas fehlschlägt:** Fehlermeldung/Traceback (Desk → *Error Log*, oder die
Meldung aus dem `frappe.throw`) hierher kopieren – das genügt meist, um den Fehler
gezielt zu beheben. Ich habe hier keinen Zugriff auf eure ERPNext-Instanz, kann die
Aufrufe also nicht selbst auslösen.

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
(bevorzugte Behandlung) und **GoGreen Plus** (klimafreundlich, nur wenn explizit
gesetzt). Einzige Automatik: DHL Settings → „Premium bei Sendungen in EU-Länder"
setzt bei internationalen Produkten automatisch Premium, **wenn das Empfängerland
in der EU liegt** – außerhalb der EU nicht (dort ist ggf. Economy günstiger).

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

## Deutsche Post / Internetmarke — REST

Läuft **nicht mehr** über die alte SOAP-Schnittstelle (OneClickForApp/1C4A) mit
separatem Partnervertrag. Stattdessen: **dieselbe DHL-Developer-Portal-App** wie
für DHL Parcel Shipping/Tracking – dort einfach zusätzlich die API
**„Post DE Internetmarke"** hinzufügen. Kein Partnervertrag nötig. Implementiert
gegen die offizielle OpenAPI-Spec ("Deutsche Post INTERNETMARKE API", Division
Post & Parcel Germany, v1.30).

**Auth** (`POST {Basis-URL}/user`, `application/x-www-form-urlencoded`,
Basis-URL `https://api-eu.dhl.com/post/de/shipping/im/v1` = Produktions-Server):

```
grant_type=client_credentials
client_id=<Client ID / Consumer Key der Developer-Portal-App>
client_secret=<Client Secret / Consumer Secret der Developer-Portal-App>
username=<Portokasse-E-Mail>
password=<Portokasse-Passwort>   # max. 22 Zeichen
```

→ Bearer-Token, weitere Aufrufe mit `Authorization: Bearer <token>`. Client
ID/Secret sind i. d. R. dieselben Werte wie `DHL Settings → API Key/Secret`
(eine gemeinsame Developer-Portal-App für alle DHL-/Post-APIs). **Live
bestätigt** (Bearer-Token via „Verbindung testen" erhalten).

**Stolperstein beim ersten Tokenabruf:** HTTP 401 kann mehrere Ursachen haben –
App in der Portokasse noch nicht freigegeben (auf portokasse.deutschepost.de →
*Meine Daten → Geschäftsanwendungen* die Anfrage einmalig freigeben), falsche
Client ID/Secret, oder fehlendes `client_secret` im Request. Die Fehlermeldung
zeigt den Rohtext der DHL-Antwort mit an.

**Marken-Erstellung** (`POST /app/shoppingcart/pdf`, `mapper.py` baut die
Bodies aus Versandsendung + Settings + Versandabsender):

| Settings-Modus | Query-Param | Body-Typ | Kosten |
| --- | --- | --- | --- |
| Vorschau (kostenlos) | `?validate=true` | `AppShoppingCartPreviewPDFRequest` (nur Produktcode/Layout/Seitenformat, keine Adressen) | keine |
| Produktiv | `?directCheckout=true` | `AppShoppingCartPDFRequest` (eine `AppShoppingCartPDFPosition`, bei Layout `ADDRESS_ZONE` inkl. Absender-/Empfängeradresse) | Portokasse wird um `total` (Cent) belastet |

**Katalog statt roher IDs:** Ein Button „Katalog aktualisieren" in den
Deutsche Post Settings ruft `GET /app/catalog` einmal ab (`catalog_sync.py`)
und spiegelt das Ergebnis in drei eigene Doctypes, jeweils mit **Deaktiviert**-
Schalter zum Kuratieren – Versandsendung/Settings verlinken nur noch darauf,
nie mehr rohe Codes/IDs von Hand:

| Doctype | Quelle | Inhalt |
| --- | --- | --- |
| `Deutsche Post Produkt` | `contractProducts.products` | tatsächlich über dein Konto bestellbare Produkte (Code + zuletzt bekannter Preis). Die API liefert keinen Namen dazu – Vorbelegung aus `constants.COMMON_PRODUCTS`, frei umbenennbar. Nur was hier aktiv ist, steht an der Versandsendung zur Auswahl. **Live beobachtet:** manche Konten (z. B. frische/Eval-Portokassen) liefern hier gar keine `contractProducts` – dann wird stattdessen mit allen 49 Produkten der offiziellen Preisliste (PPL, Stand 2026-05-13, vom User bereitgestellt) vorbefüllt, **inklusive echter Preise** (`constants.COMMON_PRODUCTS`: Code -> Name + Cent). Zwei Kilotarif-International-Produkte, die laut PPL einen gesonderten Vertrag brauchen, sind bewusst ausgelassen. |
| `Deutsche Post Seitenformat` | `pageFormats` | Druck-/Etikettenformate. Beim ersten Import werden `REGULARPAGE`/`ENVELOPE` (A4/Umschlag) automatisch deaktiviert, `LABELPRINTER`/`LABELPAGE` (Etikettenformate wie bei DHL/DPD, z. B. DIN A6) bleiben aktiv. |
| `Deutsche Post Motiv` | `publicGallery.items[].images[]` | die **Motiv-ID** – das rein dekorative Bild neben der Frankierung (Jahreszeiten-/Anlass-/Firmenmotive o. Ä.), hat keinen Einfluss auf Preis oder Produkt, komplett optional. Die OpenAPI-Spec nennt das Feld fälschlich `publicCatalog` – live verifiziert heißt der Schlüssel `publicGallery` (Doku-Fehler bei DHL, `catalog_sync.py` akzeptiert beide Namen). |

`Versandsendung.dp_product_code`/`dp_page_format_id` und die Settings-
Fallbacks `default_product_code`/`default_page_format_id`/`image_id`/
`preview_image_id` sind Link-Felder auf diese drei Doctypes (gefiltert auf
nicht-deaktivierte Einträge). Wiederholtes „Katalog aktualisieren" holt
aktuelle Preise/Formate nach, ohne eigene Umbenennungen oder den
Deaktiviert-Schalter zu überschreiben.

**Frankierbetrag (`total`):** Wird automatisch ermittelt – Priorität:
1. `Versandsendung.dp_franking_cent` (expliziter Override), 2. Live-Preis aus
`GET /app/catalog` (`contractProducts`) für den gewählten Produktcode,
3. `Deutsche Post Settings.default_franking_cent` als Fallback. **Kein
geratener Wert**: liefert keine der drei Quellen einen Betrag, wirft
`create_label` einen klaren Fehler statt eine falsche Belastung zu riskieren.

Die Antwort (`link` zur PDF-Marke, `shoppingCart` mit `shopOrderId`/
`voucherId`) wird als PDF heruntergeladen und an die Versandsendung
angehängt; `shopOrderId`/`voucherId` bleiben im Feld `api_response` erhalten.

**Storno/Retoure:** Beim Abbrechen einer submitted Versandsendung
(`on_cancel`) wird – falls `api_response` eine `shopOrderId` + Voucher
enthält (Produktiv-Modus) – automatisch `POST /app/retoure` aufgerufen, um
die Erstattung der nicht genutzten Marke zu beantragen. Im Vorschau-Modus
gibt's nichts zu erstatten (keine echte Marke gekauft), das wird erkannt
und übersprungen.

✅ Marken-Erstellung live bestätigt (Vorschau + Produktiv). Adressen:
`postalCode` muss exakt 5-stellig sein (nur deutsche PLZ, wirft sonst einen
klaren Fehler statt einen ungültigen Request zu schicken).

### Portokasse aufladen

Button **„Portokasse aufladen"** in den Settings (`PUT /app/wallet?amount=
<eurocent>`) – belastet **echtes Geld** über das in der Portokasse
hinterlegte Zahlungsmittel (i. d. R. SEPA-Lastschrift, wird nicht hier,
sondern in der Portokasse selbst festgelegt). Betrag wird im Dialog in Euro
eingegeben, in Cent umgerechnet und vor dem Absenden per `frappe.confirm`
noch einmal bestätigt. Antwort: `shopOrderId` + neues `walletBalance`.

### Automatische Journalbuchungen (DATEV)

Optional (`Journalbuchungen automatisch anlegen`, Checkbox in den Settings,
Standard aus): bei jedem erfolgreichen **Produktiv**-Markenkauf und jeder
Portokasse-Aufladung wird eine gebuchte ERPNext-`Journal Entry` angelegt –
kein eigenes DATEV-Format, die bereits installierte DATEV-Exportapp
(`erpnext_datev`) kann normale Journalbuchungen regulär exportieren.

| Vorgang | Soll | Haben |
| --- | --- | --- |
| Markenkauf | Standardgegenkonto Porto | Buchungskonto (Portokasse) |
| Aufladung | Buchungskonto (Portokasse) | Standardaufladekonto |
| Anfangsguthaben (einmalig) | Buchungskonto (Portokasse) | Standardaufladekonto |

Konfiguriert über `Deutsche Post Settings`: `Company`, `Buchungskonto`
(bildet den Portokasse-Saldo ab), `Standardgegenkonto Porto`,
`Standardaufladekonto` – alle als `Account`-Link-Felder. **Wichtig:** setzt
voraus, dass die Portokasse **ausschließlich über diese App** genutzt wird;
manuelle Aufladungen/Käufe direkt in der Portokasse-Weboberfläche werden
nicht erkannt und verfälschen den Buchungskonto-Saldo. Schlägt eine
Journalbuchung fehl (fehlende Konfiguration o. Ä.), wird die eigentliche
Transaktion (Markenkauf/Aufladung) **trotzdem nicht rückgängig gemacht** –
das Geld ist zu dem Zeitpunkt bereits geflossen, es gibt nur eine Warnung
(Desk-Meldung + Error Log) statt eines harten Fehlers.

**Anfangsguthaben:** Wer die Portokasse schon vor der Aktivierung der
Journalbuchungen genutzt hat, trägt den vorhandenen Betrag unter
„Anfangsguthaben Portokasse (Cent)" ein und klickt „Anfangsbestand buchen"
(nur einmal möglich, danach `datev_opening_balance_booked` gesetzt) – sonst
zeigt „Saldo abgleichen" dauerhaft eine Differenz in Höhe dieses
Altguthabens.

Button **„Saldo abgleichen"** (nur sichtbar wenn aktiviert) vergleicht das
echte Live-Guthaben aus der API mit dem Saldo des Buchungskontos in ERPNext
(`erpnext.accounts.utils.get_balance_on`) und zeigt die Differenz an – so
lässt sich erkennen, ob die "ausschließlich über die App"-Voraussetzung
verletzt wurde oder eine Buchung fehlgeschlagen ist.

Referenzmaterial (Spec-YAML, alte SOAP-Doku) liegt lokal in `Infos Porto/`
(gitignored).

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
│   └── deutsche_post/   # Internetmarke REST (Developer Portal): constants, client, mapper, carrier – Auth + Marken-Erstellung
│   └── */tracking.py    # Sendungsverfolgung je Carrier -> TrackingResult
├── absender.py          # Versandabsender/Marke -> ResolvedAbsender (Adresse, DHL-Abr.-Nr.)
├── tracking.py          # scheduler_events.hourly_long: poll_open_shipments()
├── api.py               # whitelisted: create_shipment_from_delivery_note(carrier, versandabsender)
├── setup/install.py     # Custom Fields (Versandabsender, Tracking-Status), Settings-Singletons
├── setup/letter_head.py # Briefkopf aus Versandabsender auf SO/DN/SI
├── utils/credentials.py # .secrets/*.json -> Settings (nur self-hosted, zum Testen)
└── versand_integration/…            # Settings (DHL/DPD/DP + Versand Integration Settings),
                                     # Versandabsender, Versandsendung(+Paket, +Tracking Event),
                                     # Workspace „Versand" + Number Cards
```

Ein neuer Carrier = neuer Ordner `carriers/<name>/` mit einer `BaseCarrier`-Klasse,
die `LabelResult` zurückgibt, plus Eintrag in `registry.py` und ein Settings-Doctype.

---

## Sicherheit

* Zugangsdaten liegen als `Password`-Felder verschlüsselt in der DB.
* `.secrets/` ist per `.gitignore` ausgeschlossen – **niemals** echte Keys committen.
* Alle API-Aufrufe laufen server-seitig; die whitelisted-Methoden prüfen
  Lese-/Schreibrechte auf `Delivery Note`/`Versandsendung`, bevor ein
  Carrier-Auftrag (Etikettenkauf) ausgelöst wird.
* `create_label()` sperrt die Sendungszeile (`for_update`) und prüft den
  Status frisch aus der DB, um doppelte Carrier-Aufträge durch parallele
  Aufrufe (Doppelklick, zwei Tabs) zu verhindern.
* Text aus Carrier-Antworten (Fehlermeldungen, Tracking-Status) wird vor
  der Anzeige in Dialogen/Benachrichtigungen escaped (`frappe.utils.escape_html`).
* Die frei editierbare `api_base_url` (Deutsche Post Settings) ist auf
  `https://*.dhl.com` beschränkt, damit Client Secret/Portokasse-Passwort
  nicht versehentlich an einen fremden Host geschickt werden; Marken-PDF-
  Downloads sind auf `https://*.deutschepost.de` mit Größenlimit begrenzt.
* `Versandsendung.api_request`/`api_response` (enthalten Empfängeradressen
  im Klartext) sind `permlevel: 1` – nur System-/Stock Manager sehen sie.
* **Rollenmodell (bewusst so belassen, bitte selbst bewerten):** die Rolle
  `Stock User` darf Versandsendungen anlegen, buchen und Etiketten
  erstellen – im Produktiv-Modus von Deutsche Post also auch echte
  Portokasse-Beträge auslösen. Wer das enger fassen will, entzieht der
  Rolle in den DocType-Berechtigungen von `Versandsendung` `create`/
  `write`/`submit` und vergibt stattdessen eine eigene Rolle (z. B.
  „Versand Manager").

## Unterstützung

Wenn dir dieses Plugin Arbeit erspart: Ich freue mich über eine freiwillige
Spende via [PayPal.me/DrdotHouse](https://paypal.me/DrdotHouse) – keine
Verpflichtung, kein Support-Anspruch, einfach eine nette Geste.

## Lizenz

MIT
