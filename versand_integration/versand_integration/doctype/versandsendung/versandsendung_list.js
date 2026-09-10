frappe.listview_settings["Versandsendung"] = {
	add_fields: ["status", "tracking_status", "docstatus"],
	get_indicator(doc) {
		if (doc.docstatus === 2) return [__("Storniert"), "red", "status,=,Storniert"];
		if (doc.status === "Fehler") return [__("Fehler"), "red", "status,=,Fehler"];
		const map = {
			"Zugestellt": "green",
			"Zustellproblem": "red",
			"Retoure": "orange",
			"In Zustellung": "blue",
			"In Transport": "blue",
			"Abgeholt": "blue",
			"Angekündigt": "light-blue",
		};
		if (doc.tracking_status && map[doc.tracking_status]) {
			return [__(doc.tracking_status), map[doc.tracking_status], `tracking_status,=,${doc.tracking_status}`];
		}
		if (doc.status === "Etikett erstellt") return [__("Etikett erstellt"), "blue", "status,=,Etikett erstellt"];
		return [__(doc.status || "Entwurf"), "gray", `status,=,${doc.status || "Entwurf"}`];
	},
};
