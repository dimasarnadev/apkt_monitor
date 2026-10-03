import frappe


def ensure_role():
    if not frappe.db.exists("Role", "APKT Operator"):
        frappe.get_doc({"doctype": "Role", "role_name": "APKT Operator", "desk_access": 1}).insert(
            ignore_permissions=True)


def after_install():
    ensure_role()
