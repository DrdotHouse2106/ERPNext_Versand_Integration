frappe.ui.form.on("Versandsendung", {
	refresh(frm) {
		frm.set_df_property("packages", "cannot_add_rows", frm.doc.status === "Etikett erstellt");

		// Nur Adressen des gewählten Kunden zur Auswahl anbieten (Standard-
		// Frappe-Muster, wie in Sales Order/Delivery Note).
		frm.set_query("customer_address", () => ({
			query: "frappe.contacts.doctype.address.address.address_query",
			filters: { link_doctype: "Customer", link_name: frm.doc.customer },
		}));

		if (
			frm.doc.carrier === "DPD" &&
			!frm.is_new() &&
			frm.doc.docstatus === 0 &&
			frm.doc.status !== "Etikett erstellt"
		) {
			frm.add_custom_button(__("Für die ganze Woche buchen"), () => {
				frappe.confirm(
					__(
						"Legt 5 Kopien dieser Sendung an (nächste 5 Werktage, je ein eigener Abholtag) und erstellt direkt die Etiketten. Fortfahren?"
					),
					() => {
						frappe.call({
							method: "versand_integration.api.create_week_shipments",
							args: { source: frm.doc.name },
							freeze: true,
							freeze_message: __("Erstelle Sendungen für die ganze Woche …"),
						}).then((r) => {
							const rows = r.message || [];
							const lines = rows.map((row) =>
								row.error
									? `${row.date}: ${__("Fehler")} – ${frappe.utils.escape_html(row.error)}`
									: `${row.date}: ${row.name} (${row.shipment_number || row.status})`
							);
							frappe.msgprint({
								title: __("Wochen-Sendungen erstellt"),
								indicator: rows.some((r) => r.error) ? "orange" : "green",
								message: lines.join("<br>"),
							});
						});
					}
				);
			});
		}

		if (frm.doc.docstatus === 0 && frm.doc.status !== "Etikett erstellt") {
			frm.add_custom_button(__("Etikett erstellen"), () => {
				frm.call({
					doc: frm.doc,
					method: "create_label",
					freeze: true,
					freeze_message: __("Versandetikett wird beim Carrier erstellt …"),
				}).then((r) => {
					if (r.message) {
						frappe.show_alert({
							message: __("Sendungsnummer {0}", [r.message.shipment_number]),
							indicator: "green",
						});
						frm.reload_doc();
						if (r.message.label_file) {
							window.open(r.message.label_file, "_blank");
						}
					}
				});
			}).addClass("btn-primary");
		}

		if (frm.doc.label_file) {
			frm.add_custom_button(__("Etikett öffnen"), () => window.open(frm.doc.label_file, "_blank"));
		}
		if (frm.doc.return_label_file) {
			frm.add_custom_button(__("Retourenlabel öffnen"), () =>
				window.open(frm.doc.return_label_file, "_blank")
			);
		}
		if (frm.doc.tracking_url) {
			frm.add_custom_button(__("Sendung verfolgen"), () => window.open(frm.doc.tracking_url, "_blank"));
		}

		if (frm.doc.shipment_number && frm.doc.carrier !== "Deutsche Post") {
			frm.add_custom_button(__("Tracking aktualisieren"), () => {
				frm.call({
					doc: frm.doc,
					method: "refresh_tracking",
					freeze: true,
					freeze_message: __("Status wird beim Carrier abgefragt …"),
				}).then((r) => {
					if (r.message) {
						frappe.show_alert({
							message: __("Status: {0}", [r.message.status || "?"]),
							indicator: r.message.status === "Zugestellt" ? "green" : "blue",
						});
						frm.reload_doc();
					}
				});
			});
		}

		const colors = {
			"Zugestellt": "green",
			"Zustellproblem": "red",
			"Retoure": "orange",
			"In Zustellung": "blue",
			"In Transport": "blue",
			"Abgeholt": "blue",
			"Angekündigt": "gray",
			"Unbekannt": "gray",
		};
		if (frm.doc.tracking_status) {
			frm.dashboard.add_indicator(
				__("Tracking: {0}", [frm.doc.tracking_status]),
				colors[frm.doc.tracking_status] || "gray"
			);
		}
		if (frm.doc.tracking_data_expired) {
			frm.dashboard.add_indicator(
				__("Carrier liefert keine Trackingdaten mehr (letzter Stand oben)"),
				"gray"
			);
		}
	},

	delivery_note(frm) {
		if (frm.doc.delivery_note) {
			frm.trigger("refresh");
		}
	},

	customer(frm) {
		if (frm.doc.delivery_note) return; // Lieferschein hat serverseitig Vorrang (validate())
		frm.set_value("customer_address", "");
		if (!frm.doc.customer) return;
		frappe.db.get_value("Customer", frm.doc.customer, "customer_primary_address").then((r) => {
			if (r.message && r.message.customer_primary_address) {
				frm.set_value("customer_address", r.message.customer_primary_address);
			}
		});
	},

	customer_address(frm) {
		if (!frm.doc.customer_address) return;
		frappe.db.get_doc("Address", frm.doc.customer_address).then((addr) => {
			// Straße komplett (inkl. Hausnummer) in receiver_street - wird beim
			// Speichern serverseitig automatisch aufgeteilt (_split_street()).
			frm.set_value("receiver_name", addr.address_title || frm.doc.customer_name || "");
			frm.set_value("receiver_address_addition", addr.address_line2 || "");
			frm.set_value("receiver_street", addr.address_line1 || "");
			frm.set_value("receiver_house_number", "");
			frm.set_value("receiver_postal_code", addr.pincode || "");
			frm.set_value("receiver_city", addr.city || "");
			if (addr.country) frm.set_value("receiver_country", addr.country);
			frm.set_value("receiver_email", addr.email_id || frm.doc.receiver_email);
			frm.set_value("receiver_phone", addr.phone || frm.doc.receiver_phone);
		});
	},
});
