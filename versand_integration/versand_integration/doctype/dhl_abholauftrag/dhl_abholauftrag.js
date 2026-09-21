frappe.ui.form.on("DHL Abholauftrag", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.status !== "Beauftragt" && frm.doc.status !== "Storniert") {
			frm.add_custom_button(__("Abholung beauftragen"), () => {
				frappe.confirm(
					__(
						"Abholauftrag jetzt bei DHL beauftragen? Bei 'Beliebige Adresse' fallen dafür ggf. Kosten an, auch wenn die Abholung nicht erfolgreich ist."
					),
					() => {
						frm.call({
							doc: frm.doc,
							method: "place_order",
							freeze: true,
							freeze_message: __("Abholauftrag wird bei DHL angelegt …"),
						}).then((r) => {
							if (r.message) {
								frappe.show_alert({
									message: __("Order-ID {0}", [r.message.order_id]),
									indicator: "green",
								});
								frm.reload_doc();
							}
						});
					}
				);
			}).addClass("btn-primary");
		}

		if (frm.doc.order_id && frm.doc.status === "Beauftragt") {
			frm.add_custom_button(__("Status abfragen"), () => {
				frm.call({
					doc: frm.doc,
					method: "refresh_pickup_status",
					freeze: true,
					freeze_message: __("Status wird bei DHL abgefragt …"),
				}).then((r) => {
					if (r.message) {
						frappe.show_alert({
							message: __("DHL-Status: {0}", [r.message.order_state || "?"]),
							indicator: "blue",
						});
						frm.reload_doc();
					}
				});
			});

			frm.add_custom_button(__("Stornieren"), () => {
				frappe.confirm(__("Abholauftrag bei DHL stornieren?"), () => {
					frm.call({
						doc: frm.doc,
						method: "cancel_pickup_order",
						freeze: true,
						freeze_message: __("Abholauftrag wird storniert …"),
					}).then(() => frm.reload_doc());
				});
			});
		}
	},

	pickup_type(frm) {
		frm.refresh();
	},
});
