frappe.ui.form.on("DPD Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Verbindung testen"), () => {
			frm.call({ doc: frm.doc, method: "test_connection", freeze: true }).then((r) => {
				if (r.message && r.message.ok) {
					frappe.msgprint({
						title: __("DPD Verbindung OK"),
						indicator: "green",
						message: (r.message.messages || []).join("<br>"),
					});
				}
			});
		});
	},
});
