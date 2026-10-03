import requests


class ApktError(Exception):
    pass


class TokenExpired(ApktError):
    pass


def graphql(url, token, query, variables, timeout=15):
    if not url:
        raise ApktError("GraphQL URL belum diisi di APKT Settings.")
    if not token:
        raise TokenExpired("Token APKT kosong.")

    response = requests.post(
        url,
        json={"query": " ".join(query.split()), "variables": variables},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=timeout,
    )
    if response.status_code == 401:
        raise TokenExpired("Token APKT expired.")
    response.raise_for_status()

    body = response.json()
    if body.get("errors"):
        raise ApktError("; ".join(str(e.get("message")) for e in body["errors"]))
    return body
