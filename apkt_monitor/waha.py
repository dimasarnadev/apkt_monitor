import time

import frappe
import requests

from apkt_monitor.logic import sanitize_text  # noqa: F401  (dipakai modul lain)


def _headers(account):
    headers = {"Content-Type": "application/json"}
    key = account.get_password("api_key", raise_exception=False)
    if key:
        headers["X-Api-Key"] = key
    return headers


def send_text(target_name, text):
    """Kirim teks ke WAHA Target. Mengembalikan True bila berhasil."""
    target = frappe.get_doc("WAHA Target", target_name)
    if not target.enabled:
        return False
    account = frappe.get_doc("WAHA Account", target.waha_account)
    if not account.enabled:
        return False

    base = account.waha_url.rstrip("/")
    headers = _headers(account)
    payload = {"session": account.session_name, "chatId": target.chat_id}

    if account.typing_simulation:
        delay = min(max(len(text) / 6, 3), 20)
        requests.post(f"{base}/api/startTyping", json=payload, headers=headers, timeout=30)
        try:
            time.sleep(delay)
        finally:
            try:
                requests.post(f"{base}/api/stopTyping", json=payload, headers=headers, timeout=30)
            except Exception:
                pass

    resp = requests.post(f"{base}/api/sendText", json={**payload, "text": text}, headers=headers, timeout=30)
    resp.raise_for_status()
    return True
