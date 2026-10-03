import json

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime

from apkt_monitor import waha
from apkt_monitor.client import ApktError, TokenExpired, graphql
from apkt_monitor.logic import (
    cache_key, date_range, get_path, render_variables, sanitize_text, should_remind,
)

MAX_PAGES = 50


def _settings():
    return frappe.get_cached_doc("APKT Settings")


def final_statuses():
    return {s.strip() for s in (_settings().final_statuses or "").splitlines() if s.strip()}


def account_dict(account):
    return {k: account.get(k) for k in ("username", "employee_name", "user_id", "id_uid", "id_up3", "id_ulp")}


def fetch_rows(poller, force=False):
    """Ambil seluruh halaman dari APKT. Hasil di-cache singkat di Redis sehingga
    poller identik dan dashboard memakai satu request yang sama."""
    settings = _settings()
    account = frappe.get_doc("APKT Account", poller.account)

    if account.token_status != "Aktif":
        raise TokenExpired(f"Token akun {account.name} berstatus {account.token_status}.")
    if not all(account.get(k) for k in ("user_id", "id_uid", "id_up3", "id_ulp")):
        raise ApktError("Profil akun APKT belum lengkap (login ulang).")

    date_from, date_to = date_range(poller.date_window_days, settings.timezone or "Asia/Jakarta")
    key = cache_key(account.name, poller.query, poller.variables, poller.page_size,
                    poller.result_path, date_from, date_to)

    if not force:
        cached = frappe.cache().get_value(key)
        if cached:
            return cached

    token = account.get_password("auth_token", raise_exception=False)
    acc = account_dict(account)
    take = int(poller.page_size)
    rows, seen, skip, total = [], set(), 0, 0

    try:
        for _ in range(MAX_PAGES):
            variables = json.loads(render_variables(poller.variables, date_from, date_to, skip, take, acc))
            body = graphql(settings.graphql_keluhan_url, token, poller.query, variables,
                           timeout=settings.request_timeout or 15)
            result = get_path(body, poller.result_path) or {}
            page = result.get("data") or []
            total = int(result.get("totalCount") or 0)
            if not page:
                break
            for row in page:
                k = get_path(row, poller.key_field) or f"id:{row.get('id')}"
                if k not in seen:
                    seen.add(k)
                    rows.append(row)
            skip += len(page)
            if skip >= total or len(page) < take:
                break
    except TokenExpired:
        _mark_expired(account)
        raise

    out = {"rows": rows, "total": total, "truncated": skip < total,
           "fetched_at": str(now_datetime()), "date_from": date_from, "date_to": date_to}
    frappe.cache().set_value(key, out, expires_in_sec=int(settings.cache_seconds or 50))
    return out


def _mark_expired(account):
    first = account.token_status == "Aktif"
    frappe.db.set_value("APKT Account", account.name, "token_status", "Expired")
    frappe.db.commit()
    if first:
        notify_token_expired(account.name)


def notify_token_expired(account_name):
    text = f"🔒 *TOKEN APKT EXPIRED*\n\nAkun {sanitize_text(account_name, 60)} perlu login ulang agar polling berjalan."
    for p in frappe.get_all("APKT Poller", filters={"account": account_name, "enabled": 1}, pluck="name"):
        for t in frappe.get_doc("APKT Poller", p).targets:
            try:
                waha.send_text(t.waha_target, text)
            except Exception:
                frappe.log_error(title="APKT: gagal kirim notifikasi token expired")


def _msg_new(row):
    return "\n".join([
        "🚨 KELUHAN BARU", "",
        f"*No Laporan:* {sanitize_text(row.get('no_laporan'), 50)}",
        f"*Pelapor:* {sanitize_text(row.get('nama_pelapor'), 100)}",
        f"*No Meter:* {sanitize_text(get_path(row, 'pelanggan_no_meter.no_meter'), 50)}",
        f"*ULP:* {sanitize_text(get_path(row, 'master_ulp.nama'), 100)}", "",
        "*Permasalahan:*", sanitize_text(row.get("permasalahan"), 500), "",
        f"*Status:* {sanitize_text(row.get('status_akhir'), 100)}",
        f"*Waktu Lapor:* {sanitize_text(row.get('waktu_lapor'), 50)}", "",
        "Mohon segera ditindaklanjuti.",
    ])


def _msg_reminder(row, minutes):
    return "\n".join([
        "⚠️ REMINDER KELUHAN", "",
        f"Status belum berubah selama ≥ {minutes} menit (belum diproses).", "",
        f"*No Laporan:* {sanitize_text(row.get('no_laporan'), 50)}",
        f"*Pelapor:* {sanitize_text(row.get('nama_pelapor'), 100)}",
        f"*ULP:* {sanitize_text(get_path(row, 'master_ulp.nama'), 100)}", "",
        "*Permasalahan:*", sanitize_text(row.get("permasalahan"), 500), "",
        f"*Status:* {sanitize_text(row.get('status_akhir'), 100)}",
        f"*Durasi:* {sanitize_text(row.get('durasi'), 50)}", "",
        "Mohon segera ditindaklanjuti.",
    ])


def sync(poller, rows):
    """Catat status + histori. Payload keluhan tidak disimpan. Mengembalikan aksi notifikasi."""
    finals = final_statuses()
    now = now_datetime()
    existing = {
        m.no_laporan: m for m in frappe.get_all(
            "APKT Monitor", filters={"poller": poller.name},
            fields=["name", "no_laporan", "status_terakhir", "is_final", "status_changed_at",
                    "new_notified_at", "last_reminder_at"])
    }
    silent = bool(poller.silent_first_run) and not existing
    actions = []

    for row in rows:
        key = get_path(row, poller.key_field)
        if not key:
            continue
        key = str(key)
        status = str(get_path(row, poller.status_field) or "").strip()
        final = 1 if status in finals else 0
        m = existing.get(key)

        if not m:
            notified = now if (silent or final) else None
            doc = frappe.get_doc({
                "doctype": "APKT Monitor", "poller": poller.name, "no_laporan": key,
                "status_terakhir": status, "is_final": final, "status_changed_at": now,
                "first_seen_at": now, "last_seen_at": now, "new_notified_at": notified,
                "history": [{"status_lama": None, "status_baru": status, "changed_at": now}],
            }).insert(ignore_permissions=True)
            if not notified:
                actions.append(("new", doc.name, row))
            continue

        if m.status_terakhir != status:
            doc = frappe.get_doc("APKT Monitor", m.name)
            doc.append("history", {"status_lama": m.status_terakhir, "status_baru": status, "changed_at": now})
            doc.update({"status_terakhir": status, "is_final": final, "status_changed_at": now,
                        "last_reminder_at": None, "last_seen_at": now})
            doc.save(ignore_permissions=True)
            m.update({"status_terakhir": status, "is_final": final, "status_changed_at": now,
                      "last_reminder_at": None})
        else:
            frappe.db.set_value("APKT Monitor", m.name, "last_seen_at", now, update_modified=False)

        if not m.is_final and not m.new_notified_at:
            actions.append(("new", m.name, row))
        elif should_remind(m.is_final, get_datetime(m.status_changed_at),
                           get_datetime(m.last_reminder_at) if m.last_reminder_at else None,
                           now, int(poller.reminder_minutes or 15)):
            actions.append(("reminder", m.name, row))

    frappe.db.commit()
    return actions


def deliver(poller, actions):
    sent_new = sent_rem = 0
    for kind, monitor, row in actions:
        flag = "notify_new" if kind == "new" else "notify_reminder"
        text = _msg_new(row) if kind == "new" else _msg_reminder(row, int(poller.reminder_minutes or 15))
        ok = 0
        for t in poller.targets:
            if not t.get(flag):
                continue
            try:
                ok += 1 if waha.send_text(t.waha_target, text) else 0
            except Exception:
                frappe.log_error(title=f"APKT: gagal kirim WAHA ({poller.name})")
        if ok:
            field = "new_notified_at" if kind == "new" else "last_reminder_at"
            frappe.db.set_value("APKT Monitor", monitor, field, now_datetime(), update_modified=False)
            frappe.db.commit()
            sent_new += kind == "new"
            sent_rem += kind == "reminder"
    return sent_new, sent_rem


def run_poller(poller_name):
    """Dijalankan background worker (queue long)."""
    poller = frappe.get_doc("APKT Poller", poller_name)
    if not poller.enabled:
        return
    frappe.db.set_value("APKT Poller", poller_name, "last_run", now_datetime(), update_modified=False)
    frappe.db.commit()

    def done(status, count=0, error=""):
        frappe.db.set_value("APKT Poller", poller_name,
                            {"last_status": status, "last_count": count, "last_error": (error or "")[:500]},
                            update_modified=False)
        frappe.db.commit()

    try:
        result = fetch_rows(poller)
        actions = sync(poller, result["rows"])
        deliver(poller, actions)
        done("OK", len(result["rows"]), "Data melebihi batas halaman." if result["truncated"] else "")
    except TokenExpired as e:
        done("Token Expired", 0, str(e))
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(title=f"APKT Poller gagal: {poller_name}")
        done("Error", 0, str(e))
