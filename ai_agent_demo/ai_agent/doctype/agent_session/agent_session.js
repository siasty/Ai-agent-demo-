frappe.ui.form.on("Agent Session", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button("Otwórz Agent Demo", () => {
                frappe.set_route("ai-agent-demo");
            });
        }
    },
});
