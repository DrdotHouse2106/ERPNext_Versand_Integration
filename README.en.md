# ERPNext Versand Integration

*[Deutsche Version](README.md)*

Frappe/ERPNext app for generating **shipping labels directly through the carrier
APIs** – no third-party middleware.

| Carrier | API | Status |
| --- | --- | --- |
| **DHL** | Parcel DE Shipping v2 (REST, OAuth2/Basic) + return shipment (services.dhlRetoure) + Paket DE Abholen v3 (pickup order) | ✅ Create + cancel label verified live; return shipment + pickup order implemented, not yet tested live |
| **DPD** | DE WebConnect (SOAP: LoginService V2.0 + ShipmentService V4.5, via `zeep`) | Login + create shipment verified live; pickup-date control (shippingDate) implemented |
| **Deutsche Post** | Internetmarke – new REST API "Post DE Internetmarke" (DHL Developer Portal, no partner contract needed anymore) | ✅ Stamp creation (preview/production) verified live; wallet top-up + optional DATEV journal entries implemented, not yet tested live |

Written and tested for **Frappe / ERPNext v16** (v15 compatibility not
verified). Python dependency: `zeep` (SOAP, for DPD).

> The **repo** is named `ERPNext_Versand_Integration`, the **Frappe app** is named
> `versand_integration` (Python module name). Frappe Cloud / `bench` read the app
> name from `pyproject.toml` – the repo name doesn't need to match.

---

## Status: Testing phase (as of 2026-09-21)

All three carriers, in the maintainer's current test instance, run against
test/sandbox credentials (DHL Parcel DE Shipping Sandbox, DPD WebConnect Stage,
a Deutsche Post "developer class" wallet account with fictional balance) –
there's no real customer data or real money involved anywhere, so live testing
against all three APIs is safe. Testing so far has been done via the API with
standalone test shipments that were deleted again afterwards (no
customer/delivery note required, no traces left in the system). **These are
the maintainer's own credentials for developing/testing this app** – every
other user enters their own real credentials in the respective settings
(sandbox or production, see "Configuration" below).

✅ **Verified live against sandbox/test credentials**
- **DHL**: "Test connection" (OAuth2), **create label** (real shipment number,
  valid PDF label downloaded and checked via the API) and **cancel**
  (`DELETE /orders`, "1 of 1 shipment successfully cancelled.") – all working
  end-to-end
- **DPD**: SOAP login (`LoginService.getAuth`, `zeep` header matching works) and
  **`storeOrders`** return a real shipment number + tracking link. The label PDF
  was missing in two consecutive runs – two root causes found and fixed
  (`splitByParcel`, then `output` being a list instead of a single object;
  commits `b38fc55`/`b8aed2e`)
- `bench migrate` basics: custom fields, billing-number table, doctypes all
  created correctly
- **Deutsche Post / Internetmarke**: auth (`POST /user`) and stamp creation
  (preview + production, `POST /app/shoppingcart/pdf`) verified live
- **Security review** (permission checks, race-condition guard on
  `create_label()`, HTML-escaping of carrier responses, SSRF protection)
  implemented and deployed – a crash it initially introduced for new/unsaved
  shipments was found and fixed (commit `6e0d9c8`), fix confirmed by the user
  on the production system
- **Manual shipment**: recipient can be pulled from the customer master data
  (customer → address) instead of typing it in by hand

🔧 **Second review round** (statically checked, not yet clicked through): cap +
carrier check for the week booking, lock against duplicate shipments per delivery note,
write-permission checks for the settings actions, base64 labels removed from the API
log, cancellation status now actually persisted (`db_set`), DHL token cache keyed by
environment/credentials with a 401 retry, WSDL cache for DPD, considerably more unit
tests and a CI pipeline (ruff + JSON checks). See ["Security"](#security) and
["Quality assurance"](#quality-assurance).

⚠️ **Not yet tested live** (code deployed/validated, but not yet clicked through)
- DPD pickup-date control + "Book for the whole week"
- DHL return shipment (`services.dhlRetoure`, return label)
- DHL pickup order (Paket DE Abholen v3) – "arbitrary address" and "agreed
  pickup location"
- Deutsche Post: wallet top-up, DATEV journal entries, balance reconciliation,
  booking the opening balance
- Multi-brand resolution (`Versandabsender`) with more than one brand,
  automatic letterhead
- Shipment tracking: background job, status sync, notifications, workspace

Not started at all yet: **per-document-type printer selection** (e.g. a
dedicated printer for shipping labels vs. customs declarations), including a
local print agent/server – concept discussed, implementation waiting on the
decision of which device should host the agent.

See ["Test procedure"](#test-procedure) below for the planned order.

---

## What the app does

| Object | Purpose |
| --- | --- |
| **DHL / DPD / Deutsche Post Settings** (each a Single) | Credentials, fallback sender, defaults, "Test connection" |
| **Versand Integration Settings** (Single) | Tracking: job on/off, interval, stop after days, notifications |
| **Versandabsender** (sender/brand) | Brand/sender profile: address, returns, letterhead, DHL billing numbers per product |
| **Versandsendung** (shipment, submittable) | Shipment for a delivery note: carrier, sender, recipient, dimensions, services, multi-parcel, label PDF, shipment number, **tracking status + history**, API log |
| **Versandsendung Paket** (child, parcel) | Individual parcels for multi-parcel shipments (DHL/DPD) |
| **DHL Abholauftrag** (pickup order, + child *DHL Abholauftrag Sendung*) | Book/cancel a DHL pickup, check its status – independent of individual shipments |
| **DHL Abholort** (pickup location) | Master data for "agreed pickup location" (synced via `GET /locations`) |
| Button **"Create shipping label"** on the *Delivery Note* | Choose carrier → creates shipment, calls the API, attaches & opens the PDF |
| Custom fields on the *Delivery Note* | `Versandsendung`, tracking number, tracking status |

Flow: **Submit delivery note → "Create shipping label" → choose carrier + sender**
→ the PDF opens, the shipment number and tracking link appear on both the
delivery note and the shipment.

**Manual shipment without a delivery note:** `Customer` is only selectable when
no delivery note is linked (otherwise the customer comes from there).
After picking a customer, its address is auto-filled from
`customer_primary_address` if one is set; the field itself only lists addresses
belonging to the selected customer (standard Frappe address lookup). Picking an
address overwrites the recipient fields (name, street, postal code, city,
country, email, phone) – saves manual retyping for repeat customers.

Cancelling a shipment:
* DHL – the shipment is deleted via `DELETE /orders`.
* DPD – not necessary (unmanifested shipments simply aren't finalized).
* Deutsche Post – a return (refund) is automatically requested via
  `POST /app/retoure`, provided a real stamp was purchased in production mode.

---

## Shipment tracking

After the label is created, the status is tracked automatically:

* **Versandsendung → "Shipment tracking" section**: status (Announced ·
  Picked up · In transit · Out for delivery · **Delivered** · Delivery
  problem · Return), carrier status text, "delivered on" and an event
  history. Button **"Refresh tracking"** for an immediate check.
* **Delivery Note**: status + "delivered on" mirrored, shown as a column/filter
  in the list view.
* **Background job** (`hourly_long`) updates all open, submitted shipments;
  stops after delivery/return or after *X* days (default 21).
* **Old shipment numbers**: carriers (e.g. DHL after ~4 weeks) eventually only
  return "Unknown"/404 for expired shipment numbers. Such a result **never**
  overwrites an already known status – otherwise old, long-delivered shipments
  would fall back to "open" again. Instead, the last known status is frozen,
  `Carrier no longer provides tracking data` is set, and automatic tracking for
  that shipment is stopped.
* **"Versand" workspace** with the *shipments in transit* / *delivery problems*
  metrics and shortcuts.
* **Notification** on *delivery problem*/*return* to every user holding a role
  (default *Stock Manager*), optionally also via email.

Configuration: **Versand Integration Settings**. Sources: DHL = "Parcel DE
Tracking" API (API key only), DPD = the public tracking.dpd.de endpoint (best
effort). Deutsche Post: some products (letters/goods shipments with "basic
tracking") return a track ID (`Voucher.trackId` from the checkout response),
which we already store in `tracking_number` – but there's **no automatic status
lookup for it yet** (no verified API reference for these IDs exists). The
background job only polls `carrier in [DHL, DPD]` anyway; in addition, "keep
tracking automatically" is disabled right at creation time for Deutsche Post
shipments (instead of leaving it permanently on but non-functional) – via
`BaseCarrier.supports_tracking` (`False` for `DeutschePostCarrier`). If a track
ID exists it's shown in the status text; for now the status can only be
checked manually on Deutsche Post's/DHL's own tracking page.

---

## Pickup (DPD/DHL) & DHL returns

### DPD – controlling the pickup date

DPD has no separate pickup API – the pickup date is set directly in the
`ShipmentService` call via `<shippingDate>`
(`carriers/dpd/pickup.py:resolve_shipping_date`). The Versandsendung (carrier
DPD) has a field **"Pickup date"** for this:

* *(empty)* – no `shippingDate` set, DPD uses the next business day.
* **Tomorrow** / **The day after tomorrow** – automatically shifted to Monday
  if it would land on a Sunday.
* **Custom day** – a specific date in the "Pickup date (date)" field.

Button **"Book for the whole week"** (DPD only, saved draft) uses
`versand_integration.api.create_week_shipments` to create five copies of the
current shipment, one per business day of the current/next week (`Custom day` +
computed date), and optionally books the label for each directly. If a single
day fails, it's logged and the remaining days still go through.

The endpoint is capped at **10 days per call** and rejects shipments whose
carrier isn't DPD (`api.MAX_WEEK_SHIPMENTS`) – every day triggers a real,
billable shipping order, and whitelisted endpoints can be called directly
without going through the button.

### DHL – return shipment

The **"DHL return shipment"** checkbox on the Versandsendung (DHL only) adds
the `dhlRetoure` service to the `/orders` call; DHL then returns a second
return label alongside the normal label, which is stored in
`return_label_file` (button "Open return label"). The billing number for the
return procedure (procedure 08) is resolved – just like for the other DHL
products – through the sender resolution chain: `Versandabsender` override →
`DHL Settings.billing_number_return` as the fallback.

### DHL – pickup order

A standalone **DHL Abholauftrag** doctype (Paket DE Abholen v3, same OAuth2
client as the shipping API) for booking a pickup independently of individual
shipments:

* **Pickup type "arbitrary address"** – enter an address freely (or pull it
  from the `Versandabsender`); per the spec DHL can charge for this even if
  the pickup doesn't succeed.
* **Pickup type "agreed pickup location"** – choose from **DHL Abholort**
  (master data via `GET /locations`, button "Refresh pickup locations" in
  **DHL Settings**).
* Shipments (child table) with an optional size (S/M/L) and customer
  reference per parcel.
* Buttons **"Book pickup"** (`POST /orders`), **"Check status"**
  (`GET /orders`), **"Cancel"** (`DELETE /orders`) – API responses land in the
  "API log" section (visible only to Administrator/Stock Manager, same as the
  Versandsendung's API log).

Not yet tested live (the feature was only recently enabled for DHL in the
developer portal) – but it can safely be run through against the DHL sandbox,
since no real data/costs are incurred there.

---

## Multiple brands / senders (`Versandabsender`)

One ERPNext Company, multiple brands (e.g. *FranceTec*, *Schmelzkammer*,
*kfz-isolierung.de*)? One **Versandabsender** record per brand:

* Sender and return address, email/phone
* **Letterhead** (Letter Head) → automatically applied to Sales Order/Delivery
  Note/Sales Invoice, as long as none is set there yet (different logos per
  brand)
* DHL/DPD overrides **only where needed** – see billing numbers below

### DHL billing numbers

Same EKP, one dedicated 14-digit number per product (digits 11–12 = product
number): enter these once, globally, in **DHL Settings → "Billing numbers per
product"**. Only if a brand has a completely separate DHL contract, set the
differing numbers as an **override** on that Versandabsender. Resolution
order: Versandabsender override → DHL Settings table → simple fallback field →
(sandbox) test number.

**Assignment** per delivery note (field *Versandabsender / brand*): customer →
sales order → delivery note (passed down the chain), otherwise the
Versandabsender flagged as *default*, otherwise the sender fields on the
carrier's Settings doctype. It can still be overridden in the dialog when
clicking "Create shipping label".

Changing the logo on documents = create a **Letter Head** per brand and link
it in the Versandabsender. No need to switch Company.

---

## Installation

### Frappe Cloud (Private App)

See [DEPLOYMENT.md](DEPLOYMENT.md) (German).

### Self-hosted Bench

```bash
cd ~/frappe-bench
bench get-app versand_integration https://github.com/DrdotHouse2106/ERPNext_Versand_Integration.git
bench --site <site> install-app versand_integration
bench --site <site> migrate
bench build --app versand_integration
```

---

## Configuration

1. Open **Desk → "DHL Settings"**.
2. `Environment` = *Sandbox* for testing.
3. `Authentication`:
   * **OAuth2** (recommended, matches the official DHL onboarding collection) –
     *API Key* + *API Secret* + GKP login. Token is cached.
     Sandbox login, if left empty: `user-valid` / `SandboxPasswort2023!`.
   * **Basic** – *API Key* (as a header) + GKP login.
     Sandbox login, if left empty: `sandy_sandbox` / `pass`.
4. `API Key` / `API Secret` from the [DHL Developer Portal](https://developer.dhl.com/).
5. Fill in **sender / return address** as a fallback – or better, create
   **`Versandabsender`** records right away (see above) and maintain billing
   numbers there per product.
6. In the sandbox, the official test billing numbers are used per product
   whenever none is configured.
7. Click **"Test connection"** → makes a `validate=true` call.
8. For **DHL Abholauftrag** (pickup API), the **"Paket DE Abholen"** API must
   additionally be added to your app in the DHL Developer Portal, on top of
   the shipping API – otherwise the pickup API's `POST /orders` responds with
   a permission error even though the same API Key/Secret work fine for
   shipping.

### Quickly loading test credentials (self-hosted only)

See [dhl_credentials.example.json](dhl_credentials.example.json) for the
format. Create a local, **not** version-controlled
`.secrets/dhl_credentials.json` (everything under `.secrets/` is gitignored)
and load it:

```bash
./scripts/load_test_credentials.sh <site-name>
# or
bench --site <site> execute versand_integration.utils.credentials.load_from_file
```

---

## Test procedure

Order for the first real test run – each step builds on the previous one; if
something fails, pick back up where it happened:

1. **Deploy** (Frappe Cloud or self-hosted) + `bench migrate`. Check: Desk
   search finds `DHL Settings`, `DPD Settings`, `Deutsche Post Settings`,
   `Versand Integration Settings`, `Versandabsender`, `Versandsendung`; the
   "Versand" workspace shows up in the sidebar.
2. Fill in **DHL Settings** (sandbox) → **"Test connection"**. This is the
   first real API call – immediately shows whether auth/billing
   number/sender address are correct.
3. Fill in **DPD Settings** (a sandbox login is provided) → **"Test
   connection"**. The biggest risk in the project (SOAP/`zeep`) – if this goes
   through, the rest is usually a formality.
4. Create a **Versandabsender** (test address + DHL sandbox billing number).
5. Submit a **Delivery Note** → **Versand → Create shipping label** → choose
   **DHL**. The PDF should open, status should read "Label created".
6. Repeat the same shipment/a second delivery note with **DPD**.
7. Click **"Refresh tracking"** on the shipment. Sandbox shipment numbers
   usually return "Unknown" – that's fine, the point is that the call
   completes **without an error**.
8. **Cancel** a shipment → verify it's cancelled with the carrier and the
   delivery note reference is cleared.
9. Create a second `Versandabsender` with a different address/letterhead,
   assign it to a test customer, submit a delivery note from it → verify the
   correct sender and letterhead are picked up.
10. Trigger the job manually instead of waiting an hour:
    `bench --site <site> execute versand_integration.tracking.poll_open_shipments`
11. **Deutsche Post**: first "Test connection" (token exchange + wallet
    balance), then "Refresh catalog" in the settings (populates
    products/page formats/motifs, see below), then create a shipment in
    **preview** mode (free) and only afterwards, with an automatically/
    deliberately set franking amount, in **production** mode (see above).
12. **New features (all safe against sandbox/test credentials, not yet
    clicked through):** create a DPD shipment with pickup date "tomorrow"/
    "custom day" and verify `shippingDate` reaches the carrier; test "Book
    for the whole week" (expect 5 copies); check "DHL return shipment" on a
    DHL shipment and verify a second label appears under "Open return
    label"; create a **DHL Abholauftrag** (both pickup types) and run
    through "Book pickup" → "Check status" → "Cancel"; in **Deutsche Post
    Settings**, test "Top up wallet" and (with journal entries enabled)
    "Reconcile balance".

**If something fails:** copy the error message/traceback here (Desk → *Error
Log*, or the message from `frappe.throw`) – that's usually enough to fix the
issue in a targeted way. I don't have access to your ERPNext instance here,
so I can't trigger the calls myself.

---

## DHL sandbox – important values

| | Value |
| --- | --- |
| Base URL | `https://api-sandbox.dhl.com/parcel/de/shipping/v2` |
| Token URL (OAuth2) | `https://api-sandbox.dhl.com/parcel/de/account/auth/ropc/v1/token` |
| OAuth2 test login | `user-valid` / `SandboxPasswort2023!` (+ your API Key/Secret as client_id/secret) |
| Basic-auth test login | `sandy_sandbox` / `pass` (+ API Key as the `dhl-api-key` header) |
| Billing no. `V01PAK` | `33333333330102` (with services), `…0101` (without) |
| Profile | `STANDARD_GRUPPENPROFIL` |
| Print format | `910-300-700` (A4) |
| Pickup API base URL (sandbox) | `https://api-sandbox.dhl.com/parcel/de/transportation/pickup/v3` |
| Pickup API base URL (production) | `https://api-eu.dhl.com/parcel/de/transportation/pickup/v3` |

Empty fields for GKP user/password and the billing number are automatically
filled in the sandbox with the test values above (depending on `auth_method`).
The pickup API (`DHL Abholauftrag`, see above) reuses the same OAuth2 token as
the shipping API – no separate login/key needed, only the base URL differs.

The select fields show readable names; the app translates them into the DHL
codes: DHL Paket (national) = `V01PAK`, DHL Paket International = `V53WPAK`,
DHL Europaket = `V54EPAK`, DHL Kleinpaket = `V62KP`, Warenpost = `V62WP`,
Warenpost International = `V66WPI`. Every product needs a matching billing
number (digits 11–12 = product number).

**Value-added services (VAS):** selectable per shipment – among others
**Premium** (priority handling) and **GoGreen Plus** (climate-friendly, only
when explicitly set). The only automation: DHL Settings → "Premium for
shipments to EU countries" automatically sets Premium on international
products **when the recipient country is in the EU** – not outside the EU
(where Economy may be cheaper).

> Vendor documentation (DHL OpenAPI spec, DPD WSDL/PDFs, Internetmarke WSDL) is
> kept locally under `Info DHL Paket/`, `Info DPD/`, `Infos Porto/` –
> gitignored.

---

## DPD (Stage)

| | Value |
| --- | --- |
| Login WSDL | `https://public-ws-stage.dpd.com/services/LoginService/V2_0/?wsdl` |
| Shipment WSDL | `https://public-ws-stage.dpd.com/services/ShipmentService/V4_5/?wsdl` |
| Test access | DELIS ID `sandboxdpd`; the password is **not** in this repo – get it from DPD and put it into `.secrets/dpd_credentials.json` (see "Quickly loading test credentials") or straight into DPD Settings |
| `sendingDepot` | comes from `getAuth` (don't set it yourself) |
| Weight | grams rounded to 10 g (`300` = 3 kg) – the app converts from kg |

Products: `CL` (Classic), `E12/E18/E830` (Express), `IE2` (Int. Express),
`PSD`/`CL2SHOP`/`SHOP2SHOP` (Shop), `MAIL`.

## Deutsche Post / Internetmarke — REST

No longer runs over the old SOAP interface (OneClickForApp/1C4A) with a
separate partner contract. Instead: **the same DHL Developer Portal app** as
for DHL Parcel Shipping/Tracking – just add the **"Post DE Internetmarke"**
API to it as well. No partner contract needed. Implemented against the
official OpenAPI spec ("Deutsche Post INTERNETMARKE API", Post & Parcel
Germany division, v1.30).

**Auth** (`POST {base URL}/user`, `application/x-www-form-urlencoded`, base
URL `https://api-eu.dhl.com/post/de/shipping/im/v1` = production server):

```
grant_type=client_credentials
client_id=<Client ID / Consumer Key of the developer-portal app>
client_secret=<Client Secret / Consumer Secret of the developer-portal app>
username=<wallet email address>
password=<wallet password>   # max. 22 characters
```

→ returns a bearer token, further calls use `Authorization: Bearer <token>`.
Client ID/Secret are usually the same values as `DHL Settings → API
Key/Secret` (one shared developer-portal app for all DHL/Post APIs). **Live
confirmed** (bearer token obtained via "Test connection").

**Gotcha on the first token request:** an HTTP 401 can have several causes –
the app not yet approved in the wallet (approve the request once at
portokasse.deutschepost.de → *My data → Business applications*), a wrong
Client ID/Secret, or a missing `client_secret` in the request. The error
message includes the raw text of DHL's response.

**Stamp creation** (`POST /app/shoppingcart/pdf`, `mapper.py` builds the
request bodies from the shipment + settings + Versandabsender):

| Settings mode | Query param | Body type | Cost |
| --- | --- | --- | --- |
| Preview (free) | `?validate=true` | `AppShoppingCartPreviewPDFRequest` (product code/layout/page format only, no addresses) | none |
| Production | `?directCheckout=true` | `AppShoppingCartPDFRequest` (one `AppShoppingCartPDFPosition`, with layout `ADDRESS_ZONE` including sender/recipient address) | wallet is charged `total` (cents) |

**Catalog instead of raw IDs:** A "Refresh catalog" button in Deutsche Post
Settings fetches `GET /app/catalog` once (`catalog_sync.py`) and mirrors the
result into three dedicated doctypes, each with a **Disabled** toggle for
curation – the shipment/settings only ever link to these, never to raw
codes/IDs by hand:

| Doctype | Source | Content |
| --- | --- | --- |
| `Deutsche Post Produkt` | `contractProducts.products` | products actually orderable under your account (code + last known price). The API doesn't return a name for these – pre-filled from `constants.COMMON_PRODUCTS`, freely renamable. Only what's active here is offered on the shipment. **Observed live:** some accounts (e.g. fresh/eval wallets) return no `contractProducts` at all here – in that case all 49 products of the official price list (PPL, dated 2026-05-13, provided by the user) are pre-filled instead, **including real prices** (`constants.COMMON_PRODUCTS`: code → name + cents). Two kilo-rate international products that, per the PPL, require a separate contract are deliberately left out. |
| `Deutsche Post Seitenformat` | `pageFormats` | print/label formats. On first import, `REGULARPAGE`/`ENVELOPE` (A4/envelope) are automatically disabled; `LABELPRINTER`/`LABELPAGE` (label formats like DHL/DPD use, e.g. DIN A6) stay active. |
| `Deutsche Post Motiv` | `publicGallery.items[].images[]` | the **motif ID** – the purely decorative image next to the franking (seasonal/occasion/company motifs etc.), has no effect on price or product, entirely optional. The OpenAPI spec incorrectly names the field `publicCatalog` – verified live, the actual key is `publicGallery` (a documentation error on DHL's side; `catalog_sync.py` accepts both names). |

`Versandsendung.dp_product_code`/`dp_page_format_id` and the settings
fallbacks `default_product_code`/`default_page_format_id`/`image_id`/
`preview_image_id` are link fields to these three doctypes (filtered to
non-disabled entries). Running "Refresh catalog" again fetches current
prices/formats without overwriting your own renames or the disabled toggle.

**Franking amount (`total`):** determined automatically – priority order:
1. `Versandsendung.dp_franking_cent` (explicit override), 2. the live price
from `GET /app/catalog` (`contractProducts`) for the chosen product code,
3. `Deutsche Post Settings.default_franking_cent` as the fallback. **No
guessed value**: if none of the three sources provides an amount,
`create_label` throws a clear error instead of risking an incorrect charge.

The response (`link` to the PDF stamp, `shoppingCart` with `shopOrderId`/
`voucherId`) is downloaded as a PDF and attached to the shipment;
`shopOrderId`/`voucherId` remain preserved in the `api_response` field.

**Cancellation/return:** When cancelling a submitted shipment (`on_cancel`) –
if `api_response` contains a `shopOrderId` + voucher (production mode) –
`POST /app/retoure` is automatically called to request a refund for the
unused stamp. In preview mode there's nothing to refund (no real stamp was
purchased), which is detected and skipped.

✅ Stamp creation confirmed live (preview + production). Addresses:
`postalCode` must be exactly 5 digits (German postal codes only, otherwise it
throws a clear error instead of sending an invalid request).

### Topping up the wallet

Button **"Top up wallet"** in the settings (`PUT /app/wallet?amount=
<eurocents>`) – charges **real money** via the payment method configured in
the wallet (typically SEPA direct debit, which is set in the wallet itself,
not here). The amount is entered in euros in a dialog, converted to cents,
and confirmed once more via `frappe.confirm` before sending. Response:
`shopOrderId` + the new `walletBalance`.

### Automatic journal entries (DATEV)

Optional (`Auto-create journal entries`, a checkbox in the settings, off by
default): on every successful **production** stamp purchase and every wallet
top-up, a posted ERPNext `Journal Entry` is created – there's no custom DATEV
format, the already-installed DATEV export app (`erpnext_datev`) can export
normal journal entries as usual.

| Operation | Debit | Credit |
| --- | --- | --- |
| Stamp purchase | Default postage offset account | Booking account (wallet) |
| Top-up | Booking account (wallet) | Default top-up account |
| Opening balance (one-time) | Booking account (wallet) | Default top-up account |

Configured via `Deutsche Post Settings`: `Company`, `Booking account` (mirrors
the wallet balance), `Default postage offset account`, `Default top-up
account` – all as `Account` link fields. **Important:** this assumes the
wallet is used **exclusively through this app**; manual top-ups/purchases done
directly in the wallet's web UI aren't detected and will throw off the
booking account's balance. If a journal entry fails (missing configuration or
similar), the actual transaction (stamp purchase/top-up) is **still not rolled
back** – the money has already moved by that point, so it only produces a
warning (desk message + error log) instead of a hard failure.

**Opening balance:** anyone who used the wallet before enabling journal
entries should enter the existing amount under "Wallet opening balance
(cents)" and click "Book opening balance" (only possible once, after which
`datev_opening_balance_booked` is set) – otherwise "Reconcile balance" will
permanently show a difference equal to that pre-existing balance.

Button **"Reconcile balance"** (only visible when enabled) compares the real
live balance from the API with the booking account's balance in ERPNext
(`erpnext.accounts.utils.get_balance_on`) and shows the difference – useful
for spotting whether the "exclusively through the app" assumption was
violated, or a journal entry failed.

Reference material (spec YAML, old SOAP docs) is kept locally under
`Infos Porto/` (gitignored).

---

## Architecture

```
versand_integration/
├── carriers/
│   ├── base.py          # BaseCarrier, LabelResult, LabelPackage (normalized)
│   ├── registry.py      # carrier name -> class
│   ├── exceptions.py    # CarrierError / CarrierConfigError / CarrierAPIError
│   ├── dhl/             # Parcel DE Shipping v2 (REST): constants, client, mapper, carrier
│   │                    # + pickup_mapper.py (builds the Paket DE Abholen v3 payload)
│   ├── dpd/             # DE WebConnect (SOAP via zeep): constants, client, mapper, carrier
│   │                    # + pickup.py (pickup-date resolution: tomorrow/day-after/custom/business days)
│   └── deutsche_post/   # Internetmarke REST (developer portal): constants, client, mapper, carrier – auth + stamp creation
│   │                    # + accounting.py (DATEV journal entries for purchase/top-up/opening balance)
│   └── */tracking.py    # per-carrier tracking -> TrackingResult
├── absender.py          # Versandabsender/brand -> ResolvedAbsender (address, DHL billing no., return address)
├── tracking.py          # scheduler_events.hourly_long: poll_open_shipments()
├── api.py               # whitelisted: create_shipment_from_delivery_note(carrier, versandabsender),
│                         # create_week_shipments(source, count) – DPD week booking, max. 10 days
├── setup/install.py     # custom fields (Versandabsender, tracking status), settings singletons
├── setup/letter_head.py # letterhead from Versandabsender onto SO/DN/SI
├── utils/credentials.py # .secrets/*.json -> settings (self-hosted only, for testing)
└── versand_integration/…            # Settings (DHL/DPD/DP + Versand Integration Settings),
                                     # Versandabsender, Versandsendung(+Paket, +Tracking Event),
                                     # DHL Abholauftrag(+Sendung)/DHL Abholort,
                                     # "Versand" workspace + number cards

.github/workflows/ci.yml             # ruff + syntax + doctype JSON checks (no bench needed)
```

Adding a new carrier = a new `carriers/<name>/` folder with a `BaseCarrier`
subclass returning a `LabelResult`, plus an entry in `registry.py` and a
Settings doctype.

---

## Security

* Credentials live as `Password` fields, encrypted in the database.
* `.secrets/` is excluded via `.gitignore` – **never** commit real keys.
* All API calls run server-side; the whitelisted methods check read/write
  permissions on `Delivery Note`/`Versandsendung` before a carrier order
  (label purchase) is triggered. The settings actions ("Test connection",
  "Refresh catalogue", "Load pickup locations", "Reconcile balance") require
  **write** permission on the respective settings – they fire real API calls
  with the stored credentials or create master data, so the read permission
  that a whitelisted document method implies is not enough.
* `create_label()` locks the shipment row (`for_update`) and re-reads the
  status fresh from the DB to prevent duplicate carrier orders from
  concurrent calls (double-click, two tabs). The same protection applies one
  level up: `create_shipment_from_delivery_note()` locks the delivery note
  first and only **then** looks for an existing shipment – otherwise two
  concurrent clicks create two shipments and buy two labels.
* `create_week_shipments()` is capped at 10 days per call and only allowed
  for DPD shipments – every day is a real, billable order.
* Text taken from carrier responses (error messages, tracking status,
  shipment numbers) is escaped before being shown in dialogs/notifications
  (`frappe.utils.escape_html`), server-side as well as in the client script.
* The freely editable `api_base_url` (Deutsche Post Settings) is restricted
  to `https://*.dhl.com`, so the client secret/wallet password can't
  accidentally be sent to a foreign host; stamp PDF downloads are restricted
  to `https://*.deutschepost.de` with a size limit. Shipment numbers are
  URL-encoded before they go into a tracking path.
* The DHL OAuth token cache is keyed by environment **and** credentials
  (hashed key). Switching sandbox ↔ production or rotating a key therefore
  takes effect immediately instead of sending a stale token for up to an
  hour; on an HTTP 401 the token is discarded once and fetched again.
* `Versandsendung.api_request`/`api_response` (contain plaintext recipient
  addresses) are `permlevel: 1` – only System/Stock Manager can see them.
  The base64 labels are stripped from the DHL response before storing (they
  are already attached as a private `File`), and both fields are capped at
  100,000 characters.
* A **disabled** `Versandabsender` is rejected even when it is set directly
  on the shipment (e.g. inherited from the customer) – otherwise labels
  would silently be printed for a brand someone deliberately retired.
* **Role model (left as-is deliberately, please evaluate for your own
  setup):** the `Stock User` role is allowed to create, submit, and create
  labels for shipments – in Deutsche Post's production mode that also means
  triggering real wallet charges. Anyone who wants to lock this down further
  should remove `create`/`write`/`submit` from that role in
  `Versandsendung`'s doctype permissions and grant a dedicated role instead
  (e.g. "Versand Manager").

## Quality assurance

Without a bench (pure code checks, also run by CI –
`.github/workflows/ci.yml` on every push/PR to `main`):

```bash
ruff check versand_integration          # configuration in pyproject.toml
python -m compileall -q versand_integration
```

CI additionally validates every doctype JSON and checks that `field_order`
and `fields` match – the most common mistake when editing those JSONs by
hand, which otherwise only shows up at `bench migrate`.

The unit tests need a Frappe site and therefore run on the bench:

```bash
bench --site <site> run-tests --app versand_integration
bench --site <site> run-tests --app versand_integration \
  --module versand_integration.versand_integration.doctype.versandsendung.test_versandsendung
```

They cover what can be checked without carrier access: street/country/product
resolution, weight logic, the generated DHL payload (including multi-parcel,
incomplete sender, return without billing number), the tracking status logic
(including the rule that "unknown" never overwrites a known status) and the
DPD pickup-date calculation. One test compares the `tracking_status` select
options in the doctype against the constants in `carriers/base.py` – if those
drift apart, a `save()` would otherwise only fail at runtime.

## Support

If this plugin saves you work: I'd appreciate a voluntary donation via
[PayPal.me/DrdotHouse](https://paypal.me/DrdotHouse) – no obligation, no
support entitlement, just a nice gesture.

## License

MIT
