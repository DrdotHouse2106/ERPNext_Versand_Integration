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
		frm.add_custom_button(__("Seitenformate aktualisieren"), () => {
			frm.call({
				doc: frm.doc,
				method: "refresh_page_formats",
				freeze: true,
				freeze_message: __("Lade Seitenformate von der Internetmarke-API …"),
			}).then((r) => {
				frappe.msgprint({
					title: __("Seitenformate aktualisiert"),
					indicator: "green",
					message: __("{0} Seitenformate gespeichert ('Deutsche Post Seitenformat').", [
						(r.message && r.message.count) || 0,
					]),
				});
			});
		});
	},
});
