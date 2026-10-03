from frappe.model.document import Document


class APKTMonitor(Document):
    def autoname(self):
        self.name = f"{self.poller}::{self.no_laporan}"
