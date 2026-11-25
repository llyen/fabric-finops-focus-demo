"""Ustawia poświadczenia źródeł danych w modelach raportów FinOps hub i uruchamia odświeżenie.

Eventhouse dostaje OAuth2 z tokenem bieżącego konta az (ważny ok. godziny, wystarcza na jedno
odświeżenie). Do odświeżania harmonogramem trzeba w usłudze zalogować się w ustawieniach modelu.
"""
import json, sys, time
import fabric_api as f
from config import WS, require

require("FABRIC_WORKSPACE_ID")
PBI = "https://analysis.windows.net/powerbi/api"
NAMES = ["FinOps hub Cost summary", "FinOps hub Rate optimization",
         "FinOps hub Invoicing", "FinOps hub Data ingestion"]
base = f"https://api.powerbi.com/v1.0/myorg/groups/{WS}/datasets"


def creds(kind, token=None):
    c = {"credentialType": kind, "encryptedConnection": "Encrypted", "encryptionAlgorithm": "None",
         "privacyLevel": "Organizational"}
    if kind == "OAuth2":
        c["credentials"] = json.dumps({"credentialData": [{"name": "accessToken", "value": token}]})
    else:
        c["credentials"] = json.dumps({"credentialData": ""})
    return {"credentialDetails": c}


models = {n: f.find_item(WS, n, "SemanticModel")["id"] for n in NAMES}
for n, sm in models.items():
    f.call("POST", f"{base}/{sm}/Default.TakeOver", resource=PBI)
    for ds in f.call("GET", f"{base}/{sm}/datasources", resource=PBI).get("value", []):
        kind = ds["connectionDetails"].get("kind")
        if kind == "AzureDataExplorer":
            body = creds("OAuth2", f.token(ds["connectionDetails"]["path"]))
        else:
            body = creds("Anonymous")
        f.call("PATCH", f"https://api.powerbi.com/v1.0/myorg/gateways/{ds['gatewayId']}/datasources/{ds['datasourceId']}",
               body, resource=PBI)
    f.call("POST", f"{base}/{sm}/refreshes", {"notifyOption": "NoNotification"}, resource=PBI)
    print("odświeżanie uruchomione:", n)

if "--wait" in sys.argv:
    pending = dict(models)
    while pending:
        time.sleep(20)
        for n, sm in list(pending.items()):
            r = f.call("GET", f"{base}/{sm}/refreshes?$top=1", resource=PBI)["value"][0]
            if r["status"] != "Unknown":
                print(n, r["status"], (r.get("serviceExceptionJson") or "")[:400])
                pending.pop(n)
