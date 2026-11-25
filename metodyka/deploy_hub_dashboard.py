"""Wdraża dashboard Real-Time Intelligence z FinOps toolkit v15 (finops-hub-dashboard.json)
jako element KQLDashboard w workspace demo, z podmienionym źródłem danych na nasz Eventhouse."""
import base64, json, os, sys
import fabric_api as f
from config import WS, EVENTHOUSE_URI as uri, FTK, require

require("FABRIC_WORKSPACE_ID", "EVENTHOUSE_QUERY_URI")
NAME = "FinOps hub dashboard"

d = json.load(open(os.path.join(FTK, "finops-hub-dashboard.json"), encoding="utf-8-sig"))
for ds in d["dataSources"]:
    ds["clusterUri"] = uri
    ds["database"] = "Hub"
d.pop("id", None)
d.pop("eTag", None)
d["title"] = NAME

payload = base64.b64encode(json.dumps(d).encode("utf-8")).decode()
definition = {"parts": [{"path": "RealTimeDashboard.json", "payload": payload, "payloadType": "InlineBase64"}]}

existing = f.find_item(WS, NAME, "KQLDashboard")
if existing:
    f.call("POST", f"/workspaces/{WS}/items/{existing['id']}/updateDefinition", {"definition": definition})
    print("zaktualizowano", existing["id"])
else:
    r = f.call("POST", f"/workspaces/{WS}/items",
               {"displayName": NAME, "type": "KQLDashboard", "definition": definition})
    print("utworzono", (r or {}).get("id"))
it = f.find_item(WS, NAME, "KQLDashboard")
print(f"https://app.fabric.microsoft.com/groups/{WS}/kustodashboards/{it['id']}")
