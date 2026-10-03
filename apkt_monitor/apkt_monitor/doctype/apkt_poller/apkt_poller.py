import json
import re

import frappe
from frappe.model.document import Document

from apkt_monitor.defaults import DEFAULT_QUERY, DEFAULT_VARIABLES
from apkt_monitor.logic import render_variables


class APKTPoller(Document):
    def before_validate(self):
        self.query = self.query or DEFAULT_QUERY
        self.variables = self.variables or DEFAULT_VARIABLES

    def validate(self):
        if (self.interval_minutes or 0) < 1:
            frappe.throw("Interval minimal 1 menit.")
        if not 1 <= (self.page_size or 0) <= 500:
            frappe.throw("Ukuran halaman harus 1-500.")
        if (self.date_window_days or 0) < 0:
            frappe.throw("Jendela hari tidak boleh negatif.")
        if re.search(r"\b(mutation|subscription)\b", self.query or "", re.I):
            frappe.throw("Hanya query GraphQL yang diizinkan (mutation/subscription ditolak).")
        sample = {"user_id": 1, "id_uid": 1, "id_up3": 1, "id_ulp": 1}
        try:
            json.loads(render_variables(self.variables, "2000-01-01", "2000-01-02", 0, 1, sample))
        except Exception as e:
            frappe.throw(f"Variables bukan JSON valid setelah template dirender: {e}")
