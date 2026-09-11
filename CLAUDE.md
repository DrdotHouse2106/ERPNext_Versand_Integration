# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Frappe/ERPNext app (`versand_integration`) that creates shipping labels directly
through carrier APIs (DHL, DPD, Deutsche Post/Internetmarke) — no third-party
middleware. Repo name (`ERPNext_Versand_Integration`) and Python module name
(`versand_integration`) intentionally differ: Frappe module names must be
lowercase snake_case, and `pyproject.toml` is the source of truth Frappe
Cloud/bench read for the actual app name — the repo name doesn't need to match.

See `README.md` for the product-level feature list, config values, and the
step-by-step manual test procedure ("Testvorgehen").

## Commands

No Frappe bench exists in this dev sandbox — there's no way to run `bench` here.
Validate changes statically instead:

```bash
# Compile every Python file
python3 -m py_compile $(find versand_integration -name "*.py")

# Validate every DocType JSON and check field_order matches the defined fields
for f in $(find versand_integration -name "*.json"); do
  python3 -c "import json; json.load(open('$f'))" || echo "BAD $f"
done
python3 -c "
import json, glob
for p in glob.glob('versand_integration/**/doctype/*/*.json', recursive=True):
    d = json.load(open(p))
    if d.get('doctype') != 'DocType' or d.get('field_order') is None: continue
    fo, fn = d['field_order'], [x['fieldname'] for x in d['fields']]
    m1, m2 = [x for x in fo if x not in fn], [x for x in fn if x not in fo]
    if m1 or m2: print(d['name'], 'MISSING', m1, 'EXTRA', m2)
"

# Lint (config in pyproject.toml)
ruff check versand_integration
```

Where a real Frappe site *is* available (production use, or a bench elsewhere):

```bash
bench --site <site> install-app versand_integration
bench --site <site> migrate
bench --site <site> run-tests --app versand_integration
bench --site <site> run-tests --app versand_integration \
  --module versand_integration.versand_integration.doctype.versandsendung.test_versandsendung

# Load local sandbox credentials from .secrets/*.json into the Settings singletons
bench --site <site> execute versand_integration.utils.credentials.load_from_file      # DHL
bench --site <site> execute versand_integration.utils.credentials.load_dpd_from_file  # DPD
bench --site <site> execute versand_integration.utils.credentials.load_dp_from_file   # Deutsche Post

# Trigger the tracking poll job manually instead of waiting for the hourly scheduler
bench --site <site> execute versand_integration.tracking.poll_open_shipments
```

### Testing against a live site via REST

When no bench/console access exists but a site API key does (`Authorization: token
<key>:<secret>`), `Versandsendung` can be created standalone — `delivery_note` is
optional, so a throwaway test doc needs no real Customer/Sales Order:

```bash
curl -X POST -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  "$SITE_URL/api/resource/Versandsendung" --data '{"carrier":"DHL","receiver_name":"...", ...}'
curl -X POST -H "$AUTH_HEADER" "$SITE_URL/api/resource/Versandsendung/<name>?run_method=create_label"
# clean up: cancel (submittable docs must be cancelled before delete)
curl -X PUT -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  "$SITE_URL/api/resource/Versandsendung/<name>" --data '{"docstatus": 2}'
curl -X DELETE -H "$AUTH_HEADER" "$SITE_URL/api/resource/Versandsendung/<name>"
```

Password-type fields (API keys, GKP/DELIS passwords) are never returned by the
REST API, so reading Settings docs back is safe. Always confirm with the user
before writing to or creating documents on a site they've indicated is
production — read-only checks (list/get) don't need that confirmation, writes do.

## Architecture

### Carrier plugin pattern

`carriers/base.py` defines the contract every carrier implements:
- `BaseCarrier.create_label(shipment) -> LabelResult`, `.cancel_label(shipment)`,
  `.track(shipment) -> TrackingResult` (default raises `TrackingNotSupported`).
- `LabelResult`/`LabelPackage`: normalized label output (base64 PDF/ZPL, shipment
  number, tracking URL, one `LabelPackage` per physical parcel).
- `TrackingResult`/`TrackingEvent` + the normalized status constants
  (`TRACK_ANNOUNCED` … `TRACK_DELIVERED`, `TRACK_PROBLEM`, `TRACK_RETURN`) that the
  `tracking_status` Select field on `Versandsendung` mirrors exactly.

Each carrier lives in its own `carriers/<name>/` folder with the same four files:
`constants.py` (endpoints, sandbox defaults, product code ⇄ label maps),
`client.py` (raw HTTP/SOAP transport, no ERPNext-document knowledge),
`mapper.py` (`Versandsendung` doc → carrier request payload), `carrier.py`
(the `BaseCarrier` subclass wiring client + mapper together). Adding a carrier
means adding that folder plus one entry in `carriers/registry.py`
(`get_carrier(name)` does a lazy `frappe.get_attr` lookup, so unrelated carriers
never get imported).

Product codes are stored as human-readable German labels in Select fields
(e.g. "DHL Paket (national)"), never the raw carrier code. Each carrier's
`constants.resolve_product()` translates label ⇄ code in both directions —
mappers call it, never read `doc.product` raw.

### Absender (sender/brand) resolution

`absender.py`'s `resolve(shipment)` returns a `ResolvedAbsender` that every
mapper's shipper/sender block is built from. Resolution order: the
`Versandsendung.versandabsender` field → the `Versandabsender` doctype record
flagged `is_default` → the carrier's own Settings singleton address fields as
final fallback. DHL billing numbers resolve per product code through the same
kind of chain: `Versandabsender` override table → the global table on
`DHL Settings` → the single fallback field → the sandbox default in
`dhl/constants.py`. This exists to support multiple brands/sender identities
under one ERPNext Company without switching Company — see README "Mehrere
Marken".

### Versandsendung lifecycle

`versandsendung.py`: draft → `create_label()` (resolves carrier + absender,
calls `carrier.create_label`, decodes/attaches the label PDF as a `File`,
auto-submits if the resolved carrier Settings' `auto_submit` allows it) →
submitted → `on_cancel()` calls `carrier.cancel_label()`. Carrier-specific
Settings lookups (auto_submit, validate_only) go through
`_carrier_settings()`/`_SETTINGS_DOCTYPE`, not a hardcoded DHL reference.

Tracking fields (`tracking_status`, `tracking_events` child table, etc.) are
all `allow_on_submit: 1` in the DocType JSON, and `refresh_tracking()` sets
`self.flags.ignore_validate = True` before `save()` — this is what lets a
submitted Versandsendung's tracking state update without re-running the full
`validate()` (which would otherwise re-sync fields from the linked Delivery
Note and reject the change as `UpdateAfterSubmitError`).

### Tracking automation

`tracking.py` (app root) is the `scheduler_events.hourly_long` job
(`poll_open_shipments`): queries submitted Versandsendungen with
`tracking_polling_active=1`, calls `refresh_tracking()` on each, stops polling
a shipment once it reaches a final status (`TRACK_FINAL` in `base.py`) or after
`Versand Integration Settings.tracking_stop_after_days`. Problem/return
notifications go out via `Notification Log` to every user holding
`tracking_notify_role`, deduped through the `tracking_problem_notified` field
so the same status doesn't re-notify every poll.

### Settings & fixtures

Per-carrier config lives in Frappe Singles (`DHL Settings`, `DPD Settings`,
`Deutsche Post Settings`); cross-cutting tracking config lives in
`Versand Integration Settings`. `setup/install.py` creates all four singletons
on install/migrate and defines the custom fields on `Delivery Note`,
`Sales Order`, `Sales Invoice`, `Customer` (declared in `hooks.py`'s
`fixtures` for clean export). `setup/letter_head.py` is a `doc_events.validate`
hook on SO/DN/SI that copies the resolved Versandabsender's `letter_head` onto
the document if none is set yet.

### Credentials

`.secrets/*.json` (gitignored, never commit) holds real test credentials for
local/self-hosted loading via `utils/credentials.py`. `dhl_credentials.example.json`
at the repo root is the tracked template — it only contains DHL's own publicly
documented sandbox values, not real secrets.
