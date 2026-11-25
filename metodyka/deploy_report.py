"""Raport Power BI nad SM_FinOps_Contoso (PBIR-Legacy, wdrozenie przez Fabric REST).

Uzycie: python deploy_report.py            (wdrozenie)
       python deploy_report.py --offline  (tylko zapis plikow do model/, z placeholderami)
"""
import base64, json, sys
from config import WS, WS_NAME, require

NAME = "FinOps Contoso Polska (dane syntetyczne)"
MODEL = "SM_FinOps_Contoso"
OFFLINE = "--offline" in sys.argv
if OFFLINE:
    SM = "<SEMANTIC_MODEL_ID>"
else:
    require("FABRIC_WORKSPACE_ID", "FABRIC_WORKSPACE_NAME")
    from fabric_api import call, find_item
    SM = find_item(WS, MODEL, "SemanticModel")["id"]
ALIAS = {"Koszty": "k", "Kalendarz": "c", "Spolki": "s", "Subskrypcje": "u"}
_n = [0]


def f(kind, ref):
    t, p = ref.split(".", 1)
    return {"kind": kind, "t": t, "p": p}


def M(ref):
    return f("Measure", ref)


def C(ref):
    return f("Column", ref)


def visual(vtype, x, y, w, h, roles, title=None, extra=None, objects=None):
    _n[0] += 1
    used = sorted({fld["t"] for fs in roles.values() for fld in fs})
    sel, proj = [], {}
    for role, fs in roles.items():
        proj[role] = []
        for fld in fs:
            qn = f'{fld["t"]}.{fld["p"]}'
            item = {fld["kind"]: {"Expression": {"SourceRef": {"Source": ALIAS[fld["t"]]}}, "Property": fld["p"]}, "Name": qn}
            if qn not in [s["Name"] for s in sel]:
                sel.append(item)
            proj[role].append({"queryRef": qn})
    sv = {"visualType": vtype, "projections": proj,
          "prototypeQuery": {"Version": 2, "From": [{"Name": ALIAS[t], "Entity": t, "Type": 0} for t in used], "Select": sel},
          "drillFilterOtherVisuals": True}
    objs = {}
    if title:
        objs["title"] = [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}},
                                         "text": {"expr": {"Literal": {"Value": f"'{title}'"}}}}}]
    if extra:
        objs.update(extra)
    if objs:
        sv["vcObjects"] = objs
    if objects:
        sv["objects"] = objects
    cfg = {"name": f"v{_n[0]:03d}", "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": _n[0], "width": w, "height": h}}],
           "singleVisual": sv}
    return {"x": x, "y": y, "z": _n[0], "width": w, "height": h, "config": json.dumps(cfg)}


def card(x, ref, title):
    return visual("card", x, 70, 240, 110, {"Values": [M(ref)]}, title,
                  objects={"categoryLabels": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}]})


def textbox(text, x, y, w, h, size=20):
    _n[0] += 1
    cfg = {"name": f"v{_n[0]:03d}", "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": _n[0], "width": w, "height": h}}],
           "singleVisual": {"visualType": "textbox", "drillFilterOtherVisuals": True, "objects": {"general": [{"properties": {"paragraphs": [
               {"textRuns": [{"value": text, "textStyle": {"fontSize": f"{size}pt", "fontWeight": "bold"}}]}]}}]}}}
    return {"x": x, "y": y, "z": _n[0], "width": w, "height": h, "config": json.dumps(cfg)}


def page(name, display, visuals):
    return {"name": name, "displayName": display, "displayOption": 1, "width": 1280, "height": 720,
            "filters": "[]", "config": "{}", "visualContainers": visuals}


slicer = lambda ref, x=1040: visual("slicer", x, 5, 230, 60, {"Values": [C(ref)]}, objects={
    "data": [{"properties": {"mode": {"expr": {"Literal": {"Value": "'Dropdown'"}}}}}]})

p1 = page("przeglad", "Przeglad i budzet", [
    textbox("Contoso Polska, koszty Azure (DANE SYNTETYCZNE, FOCUS 1.0)", 10, 10, 1000, 50),
    slicer("Spolki.Spolka"),
    card(10, "Koszty.Koszt efektywny", "Koszt efektywny"),
    card(262, "Spolki.Wykonanie budzetu", "Wykonanie budzetu"),
    card(514, "Koszty.Udzial kosztu bez poprawnego tagu", "Koszt bez poprawnego tagu"),
    card(766, "Koszty.Wykorzystanie rezerwacji", "Wykorzystanie rezerwacji"),
    card(1018, "Koszty.Stopa oszczednosci", "Stopa oszczednosci (ESR)"),
    visual("lineClusteredColumnComboChart", 10, 195, 620, 515,
           {"Category": [C("Kalendarz.Miesiac")], "Y": [M("Koszty.Koszt efektywny")], "Y2": [M("Spolki.Budzet")]},
           "Koszt efektywny i budzet w miesiacach"),
    visual("clusteredBarChart", 645, 195, 625, 250,
           {"Category": [C("Spolki.Spolka")], "Y": [M("Spolki.Wykonanie budzetu")]}, "Wykonanie budzetu wg spolki"),
    visual("tableEx", 645, 460, 625, 250,
           {"Values": [C("Spolki.Spolka"), C("Spolki.Wlasciciel budzetu"), M("Koszty.Koszt efektywny"), M("Spolki.Budzet"),
                       M("Spolki.Odchylenie od budzetu")]}, "Showback"),
])

p2 = page("alokacja", "Alokacja i tagowanie", [
    textbox("Alokacja kosztow i jakosc tagowania", 10, 10, 1000, 50),
    slicer("Spolki.Spolka"),
    visual("donutChart", 10, 70, 400, 300, {"Category": [C("Koszty.Status tagowania")], "Y": [M("Koszty.Koszt efektywny")]},
           "Koszt wg statusu tagowania"),
    visual("clusteredColumnChart", 425, 70, 845, 300,
           {"Category": [C("Kalendarz.Miesiac")], "Series": [C("Koszty.Zrodlo alokacji")], "Y": [M("Koszty.Koszt efektywny")]},
           "Zrodlo przypisania CostCenter w miesiacach"),
    visual("tableEx", 10, 385, 1260, 325,
           {"Values": [C("Koszty.ResourceName"), C("Koszty.x_ResourceGroupName"), C("Subskrypcje.Subskrypcja"),
                       C("Koszty.Tags"), C("Koszty.Status tagowania"), M("Koszty.Koszt bez poprawnego tagu")]},
           "Zasoby z brakujacym albo blednym tagiem CostCenter"),
])

p3 = page("optymalizacja", "Optymalizacja i trendy", [
    textbox("Uslugi, rezerwacje i anomalie", 10, 10, 780, 50),
    slicer("Kalendarz.Miesiac", 800),
    slicer("Spolki.Spolka"),
    visual("lineChart", 10, 70, 760, 320,
           {"Category": [C("Kalendarz.Data")], "Series": [C("Koszty.ServiceCategory")], "Y": [M("Koszty.Koszt efektywny")]},
           "Koszt dzienny wg kategorii uslug"),
    visual("tableEx", 785, 70, 485, 320,
           {"Values": [C("Koszty.CommitmentDiscountName"), M("Koszty.Wykorzystanie rezerwacji"),
                       M("Koszty.Koszt niewykorzystanych rezerwacji")]}, "Rezerwacje"),
    visual("tableEx", 10, 405, 1260, 305,
           {"Values": [C("Koszty.ServiceName"), C("Koszty.x_SkuMeterName"), M("Koszty.Koszt efektywny"),
                       M("Koszty.Koszt poprzedni miesiac"), M("Koszty.Zmiana m/m"), M("Koszty.Oszczednosci")]},
           "Uslugi i mierniki (wybierz miesiac we fragmentatorze, wtedy m/m ma sens)"),
])

report = {"config": json.dumps({"version": "5.59", "themeCollection": {"baseTheme": {"name": "CY24SU10", "version": "5.61", "type": 2}},
                                "activeSectionIndex": 0, "objects": {}}),
          "layoutOptimization": 0, "resourcePackages": [], "sections": [p1, p2, p3]}

pbir = {"version": "1.0", "datasetReference": {"byPath": None, "byConnection": {
    "connectionString": f"Data Source=\"powerbi://api.powerbi.com/v1.0/myorg/{WS_NAME}\";initial catalog={MODEL};semanticmodelid={SM}",
    "pbiServiceModelId": None, "pbiModelVirtualServerName": "sobe_wowvirtualserver", "pbiModelDatabaseName": SM,
    "name": "EntityDataSource", "connectionType": "pbiServiceXmlaStyleLive"}}}

parts = {"definition.pbir": json.dumps(pbir), "report.json": json.dumps(report, ensure_ascii=False)}

if __name__ == "__main__":
    import os
    outdir = os.path.join(os.path.dirname(__file__), "..", "model", "FinOps_Contoso.Report")
    os.makedirs(outdir, exist_ok=True)
    for p, c in parts.items():
        open(os.path.join(outdir, p), "w", encoding="utf-8").write(c)
    if OFFLINE:
        print("zapisano", outdir)
        sys.exit(0)
    payload = {"parts": [{"path": p, "payload": base64.b64encode(c.encode()).decode(), "payloadType": "InlineBase64"}
                         for p, c in parts.items()]}
    ex = find_item(WS, NAME, "Report")
    if ex:
        call("POST", f"/workspaces/{WS}/reports/{ex['id']}/updateDefinition", {"definition": payload})
        print("updated", ex["id"])
    else:
        call("POST", f"/workspaces/{WS}/reports", {"displayName": NAME, "definition": payload})
        print("created", (find_item(WS, NAME, "Report") or {}).get("id"))
