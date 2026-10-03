import json

import frappe
import requests
from frappe.utils import get_datetime, now_datetime

from apkt_monitor.client import ApktError, TokenExpired
from apkt_monitor.logic import get_path
from apkt_monitor.poller import fetch_rows, final_statuses

CAPTCHA_TTL = 300


def _settings():
    return frappe.get_cached_doc("APKT Settings")


def _flat(row, monitors, finals):
    status = str(row.get("status_akhir") or "").strip()
    m = monitors.get(str(row.get("no_laporan")))
    diam = None
    if m and m.status_changed_at and status not in finals:
        diam = int((now_datetime() - get_datetime(m.status_changed_at)).total_seconds() // 60)
    return {
        "no_laporan": row.get("no_laporan"),
        "nama_pelapor": row.get("nama_pelapor"),
        "permasalahan": row.get("permasalahan"),
        "waktu_lapor": row.get("waktu_lapor"),
        "status": status,
        "is_final": status in finals,
        "durasi": row.get("durasi"),
        "alamat": row.get("alamat_pelanggan"),
        "no_meter": get_path(row, "pelanggan_no_meter.no_meter"),
        "id_pelanggan": get_path(row, "pelanggan_no_meter.id_pelanggan"),
        "ulp": get_path(row, "master_ulp.nama"),
        "up3": get_path(row, "master_ulp.master_up3.nama"),
        "diam_menit": diam,
    }


@frappe.whitelist()
def list_pollers():
    return frappe.get_list("APKT Poller", filters={"enabled": 1}, fields=["name", "title", "last_run", "last_status"])


@frappe.whitelist()
@frappe.rate_limit(limit=60, seconds=60)
def get_keluhan(poller=None, force=0):
    """Semua keluhan saat ini (hasil poll terbaru dari cache; fetch bila cache kosong)."""
    if not poller:
        found = frappe.get_list("APKT Poller", filters={"enabled": 1}, pluck="name", limit=1)
        if not found:
            frappe.throw("Belum ada APKT Poller aktif.")
        poller = found[0]

    frappe.has_permission("APKT Poller", "read", poller, throw=True)
    doc = frappe.get_doc("APKT Poller", poller)

    try:
        result = fetch_rows(doc, force=bool(int(force)) and frappe.has_permission("APKT Poller", "write", poller))
    except TokenExpired as e:
        frappe.throw(f"{e} Login ulang pada APKT Account.", title="Token APKT")
    except (ApktError, requests.RequestException):
        frappe.log_error(title="APKT: get_keluhan gagal")
        frappe.throw("Server APKT tidak dapat dihubungi.", title="APKT")

    finals = final_statuses()
    monitors = {m.no_laporan: m for m in frappe.get_all(
        "APKT Monitor", filters={"poller": doc.name}, fields=["no_laporan", "status_changed_at"])}
    data = [_flat(r, monitors, finals) for r in result["rows"]]

    counts = {}
    for r in data:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    return {
        "poller": doc.title, "data": data, "total": result["total"], "counts": counts,
        "truncated": result["truncated"], "fetched_at": result["fetched_at"],
        "date_from": result["date_from"], "date_to": result["date_to"],
        "reminder_minutes": doc.reminder_minutes,
    }


# --------------------------------------------------------------- login APKT (captcha)

@frappe.whitelist()
def get_captcha(account):
    frappe.has_permission("APKT Account", "write", account, throw=True)
    try:
        r = requests.get(f"{_settings().auth_base_url.rstrip('/')}/auth/captcha", timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        frappe.throw("Gagal terhubung ke server APKT.")
    image = data.get("image")
    if not (isinstance(image, str) and image.startswith("data:image/") and len(image) <= 200000):
        frappe.throw("Respons captcha APKT tidak valid.")
    frappe.cache().set_value(f"apkt_captcha:{account}", data.get("captchaId"), expires_in_sec=CAPTCHA_TTL)
    return {"image": image}


@frappe.whitelist(methods=["POST"])
@frappe.rate_limit(limit=10, seconds=900)
def login(account, password, captcha):
    frappe.has_permission("APKT Account", "write", account, throw=True)
    doc = frappe.get_doc("APKT Account", account)
    captcha_id = frappe.cache().get_value(f"apkt_captcha:{account}")
    if not captcha_id:
        frappe.throw("Captcha kedaluwarsa. Muat ulang captcha.")

    try:
        r = requests.post(f"{_settings().auth_base_url.rstrip('/')}/auth", timeout=10, json={
            "username": doc.username, "password": password, "captcha": captcha, "captchaId": captcha_id})
        r.raise_for_status()
        body = r.json()
    except Exception:
        frappe.throw("Gagal terhubung ke server APKT.")

    user = body.get("user") or {}
    if not (body.get("status") and user.get("authToken")):
        frappe.throw(body.get("message") or "Login gagal.")

    doc.auth_token = user["authToken"]
    doc.token_status = "Aktif"
    doc.token_updated_at = now_datetime()
    doc.employee_name = user.get("employeeName")
    for field, key in (("user_id", "userId"), ("id_uid", "idUid"), ("id_up3", "idUp3"), ("id_ulp", "idUlp")):
        doc.set(field, int(user.get(key) or 0))
    doc.save(ignore_permissions=True)
    frappe.cache().delete_value(f"apkt_captcha:{account}")
    return {"employee_name": doc.employee_name}
