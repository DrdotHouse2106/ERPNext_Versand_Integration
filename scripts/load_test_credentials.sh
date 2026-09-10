#!/usr/bin/env bash
# Lädt .secrets/dhl_credentials.json in den DHL-Settings-Single-Doctype.
#
#   ./scripts/load_test_credentials.sh <site-name>
#
# Muss im Bench-Verzeichnis der ERPNext-Instanz laufen (dort wo `bench` verfügbar ist).
set -euo pipefail

SITE="${1:-}"
if [[ -z "$SITE" ]]; then
	echo "Usage: $0 <site-name>" >&2
	exit 1
fi

bench --site "$SITE" execute versand_integration.utils.credentials.load_from_file
echo "Fertig. Prüfe: Desk > DHL Settings > 'Verbindung testen'."
