import frappe
from frappe.utils import get_datetime, now_datetime


def dispatch_due_pollers():
    """Cron tiap menit: antrekan poller yang jatuh tempo. job_id unik mencegah tumpang tindih."""
    now = now_datetime()
    for p in frappe.get_all("APKT Poller", filters={"enabled": 1},
                            fields=["name", "interval_minutes", "last_run"]):
        due = (not p.last_run) or (now - get_datetime(p.last_run)).total_seconds() >= p.interval_minutes * 60 - 5
        if due:
            frappe.enqueue("apkt_monitor.poller.run_poller", queue="long", timeout=900,
                           job_id=f"apkt_poller::{p.name}", deduplicate=True, poller_name=p.name)
