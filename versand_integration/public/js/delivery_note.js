frappe.ui.form.on("Delivery Note", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;

		if (frm.doc.vi_versandsendung) {
			frm.add_custom_button(
				__("Versandsendung öffnen"),
				() => frappe.set_route("Form", "Versandsendung", frm.doc.vi_versandsendung),
				__("Versand")
			);
			if (frm.doc.vi_tracking_url) {
				frm.add_custom_button(
					__("Sendung verfolgen"),
					() => window.open(frm.doc.vi_tracking_url, "_blank"),
					__("Versand")
				);
			}
		} else {
			frm.add_custom_button(
				__("Versandetikett erstellen"),
				() => choose_carrier_and_create(frm),
				__("Versand")
			);
		}
	},
});

function choose_carrier_and_create(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Versandetikett erstellen"),
		fields: [
			{
				fieldname: "carrier",
				label: __("Carrier"),
				fieldtype: "Select",
				options: ["DHL", "DPD", "Deutsche Post"],
				default: "DHL",
				reqd: 1,
			},
			{
				fieldname: "hint",
				fieldtype: "HTML",
				options:
					`<p class="text-muted small">${__(
						"Empfänger, Gewicht und Produkt können danach an der Versandsendung angepasst werden."
					)}</p>`,
			},
		],
		primary_action_label: __("Erstellen"),
		primary_action(values) {
			d.hide();
			frappe.call({
				method: "versand_integration.api.create_shipment_from_delivery_note",
				args: { delivery_note: frm.doc.name, create_label: 1, carrier: values.carrier },
				freeze: true,
				freeze_message: __("Versandetikett wird bei {0} erstellt …", [values.carrier]),
				callback: (r) => {
					if (r.exc || !r.message) return;
					const res = r.message;
					frappe.show_alert({
						message: __("Versandsendung {0} – {1}", [res.name, res.shipment_number || res.status]),
						indicator: res.status === "Etikett erstellt" ? "green" : "orange",
					});
					frm.reload_doc();
					if (res.label_file) window.open(res.label_file, "_blank");
					else frappe.set_route("Form", "Versandsendung", res.name);
				},
			});
		},
	});
	d.show();
}
