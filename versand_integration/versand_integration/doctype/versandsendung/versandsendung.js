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
	},

	delivery_note(frm) {
		if (frm.doc.delivery_note) {
			frm.trigger("refresh");
		}
	},
});
