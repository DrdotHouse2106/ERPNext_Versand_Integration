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
	},
});
