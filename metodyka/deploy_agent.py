"""Tworzy lub aktualizuje Fabric Data Agent nad modelem SM_FinOps_Contoso.

Definicja wg https://learn.microsoft.com/rest/api/fabric/articles/item-management/definitions/data-agent-definition
Elementy (tabele, kolumny, miary) odczytuje z lokalnego TMDL wygenerowanego przez deploy_model.py.
"""
import base64
import json
import pathlib
import re
import sys
import uuid

from config import WS, require
from fabric_api import call, find_item

NAME = "DA_FinOps_Contoso"
MODEL = "SM_FinOps_Contoso"
TMDL = pathlib.Path(__file__).resolve().parent.parent / "model" / f"{MODEL}.SemanticModel" / "definition" / "tables"
NS = uuid.UUID("6f1d3c55-0d7e-4c43-9a51-1c0de5f1a0b1")

AI_INSTRUCTIONS = """Jesteś asystentem FinOps dla fikcyjnej grupy Contoso Polska. Odpowiadaj po polsku.
Wszystkie dane są SYNTETYCZNE i przygotowane na potrzeby demo. Nie przedstawiaj ich jako danych rzeczywistego klienta.
Dane mają format FOCUS 1.2 (FinOps Open Cost and Usage Specification), okres od maja do listopada 2026, waluta EUR.

Zasady:
- Główną miarą kosztu jest [Koszt efektywny] (EffectiveCost, koszt po amortyzacji rezerwacji i rabatach). Gdy użytkownik pyta o "koszt" bez doprecyzowania, używaj tej miary.
- [Koszt fakturowany] to BilledCost (to, co pojawia się na fakturze), [Koszt cennikowy] to ListCost. [Oszczednosci] = ListCost minus EffectiveCost, [Stopa oszczednosci] to ESR (Effective Savings Rate).
- Spółki to tabela Spolki (Data Platform, Retail, Shared, AI Lab, Logistics oraz Nieprzypisane). Spółkę przypisuje się po tagu CostCenter (kolumna Koszty[CostCenterAlokacja]).
- Budżet jest miesięczny na spółkę. [Wykonanie budzetu] powyżej 100% oznacza przekroczenie budżetu. Odpowiadając o budżecie, podawaj zawsze miesiąc lub okres.
- Status tagowania jest w kolumnie Koszty[Status tagowania]. Wartość "Poprawny" oznacza poprawny tag CostCenter; inne wartości (Brak CostCenter, Brak tagow, Bledna wielkosc liter) to problemy z alokacją. Kolumna Koszty[Zrodlo alokacji] mówi, czy spółkę ustalono z tagu (Tag), z subskrypcji (Subskrypcja), czy wcale (Brak).
- Rezerwacje: [Wykorzystanie rezerwacji] i [Koszt niewykorzystanych rezerwacji]; nazwa rezerwacji w CommitmentDiscountName.
- Do analizy w czasie używaj tabeli Kalendarz. Listopad 2026 zawiera dane tylko do połowy miesiąca, zaznacz to przy porównaniach miesiąc do miesiąca.
- Kwoty zaokrąglaj do pełnych euro i podawaj z symbolem EUR. Przy rankingach pokazuj najwyżej 10 pozycji, chyba że użytkownik poprosi o więcej.
- Jeśli danych brakuje, powiedz to wprost i nie zgaduj.

Przykładowe pytania, na które powinieneś umieć odpowiedzieć:
- Która spółka miała najwyższe wykonanie budżetu we wrześniu 2026?
- Które zasoby nie mają poprawnego tagu CostCenter i ile kosztowały?
- Jak zmienił się koszt usług AI miesiąc do miesiąca?
- Jakie jest wykorzystanie rezerwacji i która rezerwacja jest najsłabiej wykorzystana?
- Jaka jest stopa oszczędności przed wrześniem i od września?
"""

DS_INSTRUCTIONS = """Model Direct Lake na Lakehouse lh_finops. Tabela faktów Koszty (dzienne wiersze FOCUS), wymiary Kalendarz, Spolki, Subskrypcje.
Zawsze korzystaj z istniejących miar zamiast sumować kolumny samodzielnie. Kolumny FOCUS mają oryginalne nazwy angielskie (ServiceCategory, ServiceName, ResourceName, ChargeCategory), kolumny dodane mają polskie nazwy bez znaków diakrytycznych."""


def eid(*parts):
    return str(uuid.uuid5(NS, "/".join(parts)))


def unq(name):
    name = name.strip()
    return name[1:-1].replace("''", "'") if name.startswith("'") else name


def model_elements():
    tables = []
    for f in sorted(TMDL.glob("*.tmdl")):
        tname, children, desc = None, [], []
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("table "):
                tname = unq(line[6:])
                continue
            m = re.match(r"^\t(column|measure) ((?:'[^']*(?:''[^']*)*')|[^\s=]+)", line)
            if m and tname:
                kind, nm = m.group(1), unq(m.group(2))
                el = {"id": eid(tname, nm), "is_selected": True, "display_name": nm,
                      "type": f"semantic_model.{kind}"}
                if desc:
                    el["description"] = " ".join(desc)
                children.append(el)
                desc = []
            elif line.startswith("\t///"):
                desc.append(line.strip()[3:].strip())
            elif line.strip() and not line.startswith("\t\t"):
                desc = []
        tables.append({"id": eid(tname), "is_selected": True, "display_name": tname,
                       "type": "semantic_model.table", "children": children})
    return tables


def part(path, obj):
    return {"path": path, "payloadType": "InlineBase64",
            "payload": base64.b64encode(json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")).decode()}


def main():
    require("FABRIC_WORKSPACE_ID")
    model = find_item(WS, MODEL, "SemanticModel")
    folder = f"Files/Config/draft/semantic_model-{MODEL}"
    ds = {"$schema": "1.0.0", "artifactId": model["id"], "workspaceId": WS, "displayName": MODEL,
          "type": "semantic_model",
          "userDescription": "Koszty Azure w formacie FOCUS (dane syntetyczne Contoso Polska), budżety spółek, tagowanie, rezerwacje.",
          "dataSourceInstructions": DS_INSTRUCTIONS, "elements": model_elements()}
    parts = [part("Files/Config/data_agent.json", {"$schema": "2.1.0"}),
             part("Files/Config/draft/stage_config.json", {"$schema": "1.0.0", "aiInstructions": AI_INSTRUCTIONS}),
             part(f"{folder}/datasource.json", ds)]
    if "--publish" in sys.argv:
        pub = [dict(p, path=p["path"].replace("/draft/", "/published/")) for p in parts if "/draft/" in p["path"]]
        parts += pub + [part("Files/Config/publish_info.json",
                             {"$schema": "1.0.0", "description": "FinOps demo Contoso Polska, dane syntetyczne"})]
    if "--dump" in sys.argv:
        print(json.dumps(ds, ensure_ascii=False, indent=1)[:3000])
        return
    existing = find_item(WS, NAME, "DataAgent")
    if existing:
        call("POST", f"/workspaces/{WS}/items/{existing['id']}/updateDefinition", {"definition": {"parts": parts}})
        print("updated", existing["id"])
    else:
        r = call("POST", f"/workspaces/{WS}/items",
                 {"displayName": NAME, "type": "DataAgent",
                  "description": "Agent FinOps nad modelem SM_FinOps_Contoso (dane syntetyczne Contoso Polska)",
                  "definition": {"parts": parts}})
        print("created", r.get("id"), r)


if __name__ == "__main__":
    main()
