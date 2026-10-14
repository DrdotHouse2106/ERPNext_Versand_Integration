// Nur Links oeffnen, die vom Carrier bzw. vom Datei-Upload stammen koennen:
// https-URLs und private Dateianhaenge. Ein per REST gesetztes javascript:-
// Schema wuerde sonst im Desk-Origin ausgefuehrt.
function vi_safe_open(url) {
	if (typeof url === "string" && (/^https:\/\//i.test(url) || url.startsWith("/private/files/"))) {
		window.open(url, "_blank");
	} else {
		frappe.show_alert({ message: __("Link wurde nicht geöffnet (unzulässiges Format)."), indicator: "red" });
	}
}

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
					() => vi_safe_open(frm.doc.vi_tracking_url),
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
				fieldname: "versandabsender",
				label: __("Versandabsender / Marke"),
				fieldtype: "Link",
				options: "Versandabsender",
				default: frm.doc.vi_versandabsender || "",
				description: __("Leer = Standard-Absender."),
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
				args: {
					delivery_note: frm.doc.name,
					create_label: 1,
					carrier: values.carrier,
					versandabsender: values.versandabsender || null,
				},
				freeze: true,
				freeze_message: __("Versandetikett wird bei {0} erstellt …", [values.carrier]),
				callback: (r) => {
					if (r.exc || !r.message) return;
					const res = r.message;
					// shipment_number kommt vom Carrier (roh) - vor dem HTML-Rendering escapen.
					const shipment_number = res.shipment_number
						? frappe.utils.escape_html(res.shipment_number)
						: res.status;
					frappe.show_alert({
						message: __("Versandsendung {0} – {1}", [res.name, shipment_number]),
						indicator: res.status === "Etikett erstellt" ? "green" : "orange",
					});
					frm.reload_doc();
					if (res.label_file) vi_safe_open(res.label_file);
					else frappe.set_route("Form", "Versandsendung", res.name);
				},
			});
		},
	});
	d.show();
}
