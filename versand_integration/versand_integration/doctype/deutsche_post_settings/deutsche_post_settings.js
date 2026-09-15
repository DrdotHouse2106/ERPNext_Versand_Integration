frappe.ui.form.on("Deutsche Post Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Verbindung testen"), () => {
			frm.call({ doc: frm.doc, method: "test_connection", freeze: true }).then((r) => {
				if (r.message && r.message.ok) {
					frappe.msgprint({
						title: __("Internetmarke Verbindung OK"),
						indicator: "green",
						message: (r.message.messages || []).join("<br>"),
					});
				}
			});
		});
		frm.add_custom_button(__("Katalog aktualisieren"), () => {
			frm.call({
				doc: frm.doc,
				method: "refresh_catalog",
				freeze: true,
				freeze_message: __("Lade Produkte/Seitenformate/Motive von der Internetmarke-API …"),
			}).then((r) => {
				const m = r.message || {};
				frappe.msgprint({
					title: __("Katalog aktualisiert"),
					indicator: "green",
					message: __(
						"{0} Produkte, {1} Seitenformate, {2} Motive gespeichert. Nicht Gewünschtes kann dort jeweils über 'Deaktiviert' ausgeblendet werden.",
						[m.products || 0, m.page_formats || 0, m.motifs || 0]
					),
				});
			});
		});
	},
});
