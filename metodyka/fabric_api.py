"""Minimalny klient Fabric REST API oparty o token z Azure CLI (konto zalogowane przez az login)."""
import json
import shutil
import subprocess
import time

import requests

from config import SUBSCRIPTION

API = "https://api.fabric.microsoft.com/v1"
_tokens = {}


def token(resource="https://api.fabric.microsoft.com"):
    t = _tokens.get(resource)
    if t and t[1] > time.time() + 300:
        return t[0]
    cmd = [shutil.which("az"), "account", "get-access-token", "--resource", resource, "-o", "json"]
    if SUBSCRIPTION:
        cmd += ["--subscription", SUBSCRIPTION]
    out = subprocess.check_output(cmd, text=True)
    d = json.loads(out)
    _tokens[resource] = (d["accessToken"], d["expires_on"])
    return d["accessToken"]


def call(method, path, body=None, resource="https://api.fabric.microsoft.com", base=API, wait=True):
    url = path if path.startswith("http") else f"{base}{path}"
    r = requests.request(method, url, json=body,
                         headers={"Authorization": f"Bearer {token(resource)}"})
    if r.status_code == 202 and wait and "Location" in r.headers:
        loc = r.headers["Location"]
        while True:
            time.sleep(int(r.headers.get("Retry-After", 5)))
            r = requests.get(loc, headers={"Authorization": f"Bearer {token(resource)}"})
            if r.status_code != 200:
                continue
            st = r.json().get("status")
            if st in ("Succeeded", "Failed", "Cancelled", None):
                if st == "Failed":
                    raise RuntimeError(r.text)
                res = requests.get(loc + "/result", headers={"Authorization": f"Bearer {token(resource)}"})
                return res.json() if res.status_code == 200 and res.content else r.json()
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {url} -> {r.status_code}: {r.text}")
    return r.json() if r.content else {}


def items(ws, type_=None):
    q = f"?type={type_}" if type_ else ""
    return call("GET", f"/workspaces/{ws}/items{q}").get("value", [])


def find_item(ws, name, type_):
    return next((i for i in items(ws, type_) if i["displayName"] == name), None)


def kusto_mgmt(query_uri, db, csl):
    r = requests.post(f"{query_uri}/v1/rest/mgmt",
                      json={"db": db, "csl": csl},
                      headers={"Authorization": f"Bearer {token('https://kusto.kusto.windows.net')}"})
    if r.status_code >= 400:
        raise RuntimeError(f"KQL mgmt {r.status_code}: {r.text[:2000]}")
    return r.json()


def kusto_query(query_uri, db, csl):
    r = requests.post(f"{query_uri}/v2/rest/query",
                      json={"db": db, "csl": csl},
                      headers={"Authorization": f"Bearer {token('https://kusto.kusto.windows.net')}"})
    if r.status_code >= 400:
        raise RuntimeError(f"KQL query {r.status_code}: {r.text[:2000]}")
    frames = r.json()
    for f in frames:
        if f.get("FrameType") == "DataTable" and f.get("TableKind") == "PrimaryResult":
            cols = [c["ColumnName"] for c in f["Columns"]]
            return [dict(zip(cols, row)) for row in f["Rows"]]
    return []
