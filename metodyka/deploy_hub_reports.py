"""Wdraża raporty Power BI w wersji KQL z FinOps toolkit v15 (PowerBI-kql.zip) do workspace demo.

Z każdego .pbit bierze DataModelSchema (TMSL) jako model.bim z ustawionym parametrem Cluster URL
i Report/Layout jako report.json (format legacy), podpięty do wdrożonego modelu.
Raporty Governance i Workload optimization pomijamy, bo wymagają też Azure Resource Graph.
"""
import base64, io, json, os, sys, zipfile
import fabric_api as f
from config import WS, WS_NAME, EVENTHOUSE_URI, FTK, require

require("FABRIC_WORKSPACE_ID", "FABRIC_WORKSPACE_NAME", "EVENTHOUSE_QUERY_URI")
REPORTS = {
    "CostSummary.kql.pbit": "FinOps hub Cost summary",
    "RateOptimization.kql.pbit": "FinOps hub Rate optimization",
    "Invoicing.kql.pbit": "FinOps hub Invoicing",
    "DataIngestion.kql.pbit": "FinOps hub Data ingestion",
}
cluster = EVENTHOUSE_URI


def b64(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return base64.b64encode(data).decode()


def part(path, data):
    return {"path": path, "payload": b64(data), "payloadType": "InlineBase64"}


def upsert(name, type_, definition):
    it = f.find_item(WS, name, type_)
    if it:
        f.call("POST", f"/workspaces/{WS}/items/{it['id']}/updateDefinition", {"definition": definition})
    else:
        f.call("POST", f"/workspaces/{WS}/items", {"displayName": name, "type": type_, "definition": definition})
    return f.find_item(WS, name, type_)["id"]


def utf16(raw):
    return raw.decode("utf-16-le").lstrip("\ufeff")


only = sys.argv[1:]
z = zipfile.ZipFile(os.path.join(FTK, "PowerBI-kql.zip"))
for pbit, name in REPORTS.items():
    if only and pbit not in only:
        continue
    p = zipfile.ZipFile(io.BytesIO(z.read(pbit)))
    bim = json.loads(utf16(p.read("DataModelSchema")))
    for e in bim["model"].get("expressions", []):
        if e["name"] == "Cluster URL":
            e["expression"] = f'"{cluster}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'
    bim["name"] = name
    pbism = json.dumps({"version": "1.0", "settings": {}})
    sm_id = upsert(name, "SemanticModel", {"parts": [part("model.bim", json.dumps(bim)), part("definition.pbism", pbism)]})

    parts = [part("report.json", utf16(p.read("Report/Layout"))),
             part("definition.pbir",                           json.dumps({"version": "1.0", "datasetReference": {"byPath": None, "byConnection": {
                              "connectionString": f"Data Source=\"powerbi://api.powerbi.com/v1.0/myorg/{WS_NAME}\";initial catalog={name};semanticmodelid={sm_id}",
                              "pbiServiceModelId": None, "pbiModelVirtualServerName": "sobe_wowvirtualserver",
                              "pbiModelDatabaseName": sm_id, "name": "EntityDataSource",
                              "connectionType": "pbiServiceXmlaStyleLive"}}}))]
    for n in p.namelist():
        if n.startswith("Report/StaticResources/") and not n.endswith("/"):
            parts.append(part(n[len("Report/"):], p.read(n)))
    rep_id = upsert(name, "Report", {"parts": parts})
    print(f"{name}: model {sm_id}, raport {rep_id}")
