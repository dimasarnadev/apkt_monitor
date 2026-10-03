"""bench --site <site> execute apkt_monitor.migrate_sqlite.import_sqlite \
     --kwargs "{'path': '/path/database.sqlite', 'poller': 'Nama Poller'}"
Mengimpor status + histori dari SQLite lama (skema baru atau lama, tanpa payload)."""
import sqlite3

import frappe
from frappe.utils import get_datetime


def import_sqlite(path, poller):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    cols = {c["name"] for c in con.execute("PRAGMA table_info(keluhan_monitoring)")}
    final = ("Batal", "Selesai")
    has_hist = bool(con.execute("SELECT name FROM sqlite_master WHERE name='keluhan_status_history'").fetchone())
    done = 0

    for r in con.execute("SELECT * FROM keluhan_monitoring"):
        no = r["no_laporan"]
        if frappe.db.exists("APKT Monitor", f"{poller}::{no}"):
            continue
        status = (r["status_terakhir"] if "status_terakhir" in cols else "") or ""
        first = get_datetime(r["first_seen_at"]).replace(tzinfo=None)
        changed = get_datetime(r["status_changed_at"] or r["first_seen_at"]).replace(tzinfo=None)
        hist = []
        if has_hist:
            hist = [{"status_lama": h["status_lama"], "status_baru": h["status_baru"],
                     "changed_at": get_datetime(h["changed_at"]).replace(tzinfo=None)}
                    for h in con.execute("SELECT * FROM keluhan_status_history WHERE no_laporan=? ORDER BY id", (no,))]
        if not hist:
            hist = [{"status_lama": None, "status_baru": status, "changed_at": changed}]
        frappe.get_doc({
            "doctype": "APKT Monitor", "poller": poller, "no_laporan": no, "status_terakhir": status,
            "is_final": 1 if status.strip() in final else 0, "status_changed_at": changed,
            "first_seen_at": first, "last_seen_at": changed, "new_notified_at": first, "history": hist,
        }).insert(ignore_permissions=True)
        done += 1
    frappe.db.commit()
    print(f"{done} keluhan diimpor.")
