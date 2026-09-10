frappe.ui.form.on("Versandsendung", {
	refresh(frm) {
		frm.set_df_property("packages", "cannot_add_rows", frm.doc.status === "Etikett erstellt");

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
	},

	delivery_note(frm) {
		if (frm.doc.delivery_note) {
			frm.trigger("refresh");
		}
	},
});
