import frappe


def set_letter_head_from_absender(doc, method=None):
	"""Setzt den Briefkopf aus dem Versandabsender/der Marke – nur wenn noch keiner gewählt ist."""
	absender = doc.get("vi_versandabsender")
	if not absender or doc.get("letter_head"):
		return
	letter_head = frappe.db.get_value("Versandabsender", absender, "letter_head")
	if letter_head:
		doc.letter_head = letter_head
