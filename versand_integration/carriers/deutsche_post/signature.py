"""Partner-Signatur für 1C4A V3.

keystring = PARTNER_ID :: REQUEST_TIMESTAMP :: KEY_PHASE :: SCHLUESSEL
Whitespace wird entfernt, dann SHA-512 (Hex).
(Quelle: offizielle Postman-Collection, prerequest-Script.)
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime


def request_timestamp(now: datetime | None = None) -> str:
	now = now or datetime.now()
	return now.strftime("%d%m%Y-%H%M%S")


def partner_signature(partner_id: str, timestamp: str, key_phase: str, key: str) -> str:
	keystring = f"{partner_id}::{timestamp}::{key_phase}::{key}"
	cleanstring = re.sub(r"\s+", "", keystring)
	return hashlib.sha512(cleanstring.encode("utf-8")).hexdigest()
