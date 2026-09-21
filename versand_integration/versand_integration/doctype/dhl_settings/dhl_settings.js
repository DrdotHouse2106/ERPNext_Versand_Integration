frappe.ui.form.on("DHL Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Verbindung testen"), () => {
			frm.call({
				doc: frm.doc,
				method: "test_connection",
				freeze: true,
				freeze_message: __("Teste Verbindung zur DHL-API …"),
			}).then((r) => {
				if (r.message && r.message.ok) {
					frappe.msgprint({
						title: __("Verbindung OK ({0})", [r.message.environment]),
						indicator: "green",
						message: (r.message.messages || []).join("<br>"),
					});
				}
			});
		});
		frm.add_custom_button(__("Abholorte aktualisieren"), () => {
			frm.call({
				doc: frm.doc,
				method: "refresh_pickup_locations",
				freeze: true,
				freeze_message: __("Lade vereinbarte Abholorte von der DHL-API …"),
			}).then((r) => {
				frappe.msgprint({
					title: __("Abholorte aktualisiert"),
					indicator: "green",
					message: __("{0} Abholorte gespeichert ('DHL Abholort').", [(r.message && r.message.count) || 0]),
				});
			});
		}, __("Abholung"));
	},
});
