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
		frm.add_custom_button(__("Portokasse aufladen"), () => charge_wallet(frm), __("Portokasse"));
		if (frm.doc.datev_enabled) {
			frm.add_custom_button(__("Saldo abgleichen"), () => reconcile_balance(frm), __("Portokasse"));
		}
	},
});

function reconcile_balance(frm) {
	frm.call({
		doc: frm.doc,
		method: "reconcile_wallet_balance",
		freeze: true,
		freeze_message: __("Vergleiche Portokasse-Guthaben mit Buchungskonto …"),
	}).then((r) => {
		const res = r.message || {};
		const live = (res.live_balance_cent / 100).toFixed(2);
		const ledger = (res.ledger_balance_cent / 100).toFixed(2);
		const diff = (res.diff_cent / 100).toFixed(2);
		frappe.msgprint({
			title: res.matches ? __("Saldo stimmt überein") : __("Saldo weicht ab"),
			indicator: res.matches ? "green" : "red",
			message: res.matches
				? __("Portokasse und Buchungskonto stimmen überein: {0} €.", [live])
				: __(
						"Portokasse (live): {0} €<br>Buchungskonto (ERPNext): {1} €<br>Differenz: {2} € – " +
							"vermutlich wurde die Portokasse auch außerhalb dieser App genutzt (manuelle " +
							"Aufladung/Kauf) oder eine Journalbuchung ist fehlgeschlagen (Error Log prüfen).",
						[live, ledger, diff]
					),
		});
	});
}

function charge_wallet(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Portokasse aufladen"),
		fields: [
			{
				fieldname: "warning",
				fieldtype: "HTML",
				options: `<div class="alert alert-danger">${__(
					"Das belastet echtes Geld über das in der Portokasse hinterlegte Zahlungsmittel (i. d. R. SEPA-Lastschrift) – nicht rückgängig zu machen."
				)}</div>`,
			},
			{
				fieldname: "amount",
				label: __("Betrag (€)"),
				fieldtype: "Currency",
				reqd: 1,
				description: __("Wird auf volle Cent gerundet und als Ganzzahl in Cent an die API übergeben."),
			},
		],
		primary_action_label: __("Jetzt aufladen"),
		primary_action(values) {
			const amount_cent = Math.round(values.amount * 100);
			frappe.confirm(
				__("{0} € jetzt wirklich von der Portokasse aufladen (echte Abbuchung)?", [
					values.amount,
				]),
				() => {
					d.hide();
					frm.call({
						doc: frm.doc,
						method: "charge_wallet",
						args: { amount_cent },
						freeze: true,
						freeze_message: __("Portokasse wird aufgeladen …"),
					}).then((r) => {
						const res = r.message || {};
						let msg = __("Neues Guthaben: {0} €.", [
							res.wallet_balance != null ? (res.wallet_balance / 100).toFixed(2) : "?",
						]);
						if (res.booking_warning) {
							msg += `<br><span class="text-warning">${frappe.utils.escape_html(
								res.booking_warning
							)}</span>`;
						}
						frappe.msgprint({
							title: __("Portokasse aufgeladen"),
							indicator: res.booking_warning ? "orange" : "green",
							message: msg,
						});
					});
				}
			);
		},
	});
	d.show();
}
