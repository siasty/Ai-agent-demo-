frappe.ui.form.on("Agent Log", {
    refresh(frm) {
        // Pole tylko do odczytu – log generowany automatycznie
        frm.set_read_only();
    },
});
