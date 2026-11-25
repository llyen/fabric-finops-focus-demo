"""Generator SYNTETYCZNYCH danych kosztowych w formacie FOCUS 1.0 (kolumny jak w eksporcie
Cost Management "Cost and usage details (FOCUS)" 1.0). Fikcyjna grupa "Contoso Polska".

Ceny katalogowe (ListUnitPrice) pochodzą z Azure Retail Prices API (EUR, westeurope,
plik dane/retail_prices_raw.json). Wolumeny zużycia, rabat EA, tagi i zdarzenia są wymyślone
na potrzeby demo i opisane w README.

Wynik:
  dane/focus_syntetyczne/<yyyy>/<mm>/contoso-polska/<ingestionId>__part0.parquet  (układ dla FinOps hub, kontener ingestion)
  dane/focus_syntetyczne_all.parquet  (jeden plik do Lakehouse)
  dane/dim_spolki.csv, dane/budzety.csv
"""
import json
import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dane"
RNG = np.random.default_rng(20261119)

START = date(2026, 5, 1)
END = date(2026, 11, 14)  # włącznie; listopad niepełny
EA_DISCOUNT = 0.05  # fikcyjny rabat EA na usługi Microsoft (ContractedCost)
CUR = "EUR"
EUR_USD = 1.08  # fikcyjny kurs do kolumn *InUsd

prices = json.load(open(OUT / "retail_prices_raw.json"))


def price(key, **flt):
    for i in prices[key]:
        if all((i.get(k) == v) if not callable(v) else v(i.get(k)) for k, v in flt.items()):
            return i
    raise KeyError(f"{key} {flt}")


P = {
    "d4s": price("vm_d4s", type="Consumption", productName="Virtual Machines Dsv5 Series", skuName="Standard_D4s_v5"),
    "d4s_ri": price("vm_d4s", type="Reservation", reservationTerm="1 Year"),
    "e8s": price("vm_e8s", type="Consumption", productName="Virtual Machines Esv5 Series", skuName="E8s v5"),
    "e8s_win": price("vm_e8s", type="Consumption", productName="Virtual Machines Esv5 Series Windows", skuName="E8s v5"),
    "e8s_ri": price("vm_e8s", type="Reservation", reservationTerm="1 Year"),
    "nc": price("vm_nc", type="Consumption", productName="NCads A100 v4 Series Linux", skuName="Standard_NC24ads_A100_v4"),
    "sqldb": price("sqldb", type="Consumption"),
    "pg": price("pgflex", type="Consumption"),
    "app": price("appsvc", type="Consumption", productName="Azure App Service Premium v3 Plan - Linux"),
    "blob": price("storage", meterName="Hot LRS Data Stored", tierMinimumUnits=0.0),
    "loga": price("loga", meterName="Analytics Logs Data Ingestion", retailPrice=lambda v: v > 0),
    "dbx_jobs": price("dbx", meterName="Premium Jobs Compute DBU"),
    "dbx_sql": price("dbx", meterName="Premium Serverless SQL DBU"),
    "bw": price("bw", productName="Bandwidth - Routing Preference: Internet", tierMinimumUnits=lambda v: v and v > 0),
    "disk_p30": price("disk", type="Consumption", meterName="P30 LRS Disk"),
    "gpt4o_in": price("aoai", meterName="gpt-4o-0806-Inp-glbl Tokens"),
    "gpt4o_out": price("aoai", meterName="gpt-4o-0806-Outp-glbl Tokens"),
    "mini_in": price("aoai", meterName="gpt-4o-mini-0718-Inp-regnl Tokens"),
    "mini_out": price("aoai", meterName="gpt-4o-mini-0718-Outp-regnl Tokens"),
    "onelake": price("fabric", meterName="OneLake Storage Hot Data Stored"),
    "fabric_overage": price("fabric", meterName="Capacity Overage Capacity Usage CU"),
    "fabric_ri": price("fabric_res", armRegionName="westeurope", reservationTerm="1 Year"),
}
FABRIC_METERS = {
    "Spark Memory Optimized Capacity Usage CU": 0.34,
    "Power BI Capacity Usage CU": 0.24,
    "Data Warehouse Capacity Usage CU": 0.17,
    "Data Movement Capacity Usage CU": 0.09,
    "Data Orchestration Capacity Usage CU": 0.06,
    "Eventhouse Capacity Usage CU": 0.05,
    "Copilot and AI Capacity Usage CU": 0.05,
}
for m in FABRIC_METERS:
    P[m] = price("fabric", meterName=m)
FABRIC_CU = P["Power BI Capacity Usage CU"]["retailPrice"]
FABRIC_RI_HOURLY = P["fabric_ri"]["retailPrice"] / 8760  # cena roczna za 1 CU

BILLING_ACCOUNT_ID = "/providers/Microsoft.Billing/billingAccounts/90000001"
BILLING_ACCOUNT_NAME = "Contoso Polska (DANE SYNTETYCZNE)"


def gid(*parts):
    return str(uuid.UUID(hashlib.md5("|".join(parts).encode()).hexdigest()))


SPOLKI = [
    # CostCenter, Spółka, właściciel budżetu, budżet miesięczny EUR (fikcyjny)
    ("CC-100", "Contoso Retail", "anna.nowak@contoso.example", 9000),
    ("CC-200", "Contoso Logistics", "piotr.kowalski@contoso.example", 2500),
    ("CC-300", "Contoso Data Platform", "marta.wisniewska@contoso.example", 19500),
    ("CC-400", "Contoso AI Lab", "tomasz.zielinski@contoso.example", 3500),
    ("CC-900", "Contoso Shared Services", "it.platform@contoso.example", 3500),
]
CC = {s[1]: s[0] for s in SPOLKI}

SUBS = {
    "retail-prod": ("Contoso Retail", "prod"),
    "retail-dev": ("Contoso Retail", "dev"),
    "logistics-prod": ("Contoso Logistics", "prod"),
    "logistics-dev": ("Contoso Logistics", "dev"),
    "dataplatform-prod": ("Contoso Data Platform", "prod"),
    "dataplatform-dev": ("Contoso Data Platform", "dev"),
    "ailab": ("Contoso AI Lab", "dev"),
    "shared-connectivity": ("Contoso Shared Services", "prod"),
}
SUB_ID = {k: gid("sub", k) for k in SUBS}

resources = []  # definicje zasobów


def res(sub, rg, rp_type, name, kind, service, category, pkey, *, qty=1.0, start=START, end=END,
        tags="full", app=None, pattern="24x7", rtype_name=None, region="westeurope", extra=None):
    spolka, env = SUBS[sub]
    rid = f"/subscriptions/{SUB_ID[sub]}/resourcegroups/{rg}/providers/{rp_type}/{name}".lower()
    if tags == "full":
        t = {"CostCenter": CC[spolka], "Spolka": spolka, "env": env, "app": app or rg.replace("rg-", "")}
    elif tags == "partial":
        t = {"env": env, "owner": "dev-team"}
    elif tags == "badcase":
        t = {"costcenter": CC[spolka].lower(), "Env": env.upper()}
    else:
        t = {}
    resources.append(dict(sub=sub, rg=rg, rp_type=rp_type, name=name, kind=kind, service=service,
                          category=category, pkey=pkey, qty=qty, start=start, end=end, tags=t,
                          pattern=pattern, rtype_name=rtype_name, rid=rid, region=region, extra=extra or {}))


VM = "microsoft.compute/virtualmachines"
# Contoso Retail
for i in range(1, 7):
    res("retail-prod", "rg-eshop-prod", VM, f"vm-eshop-app-{i:02}", "vm", "Virtual Machines", "Compute", "d4s",
        app="eshop", rtype_name="Virtual machine", extra={"ri": "d4s" if i <= 4 else None})
res("retail-prod", "rg-eshop-prod", "microsoft.sql/servers/databases", "sql-eshop-prod/eshopdb", "sqldb",
    "Azure SQL Database", "Databases", "sqldb", app="eshop", rtype_name="SQL database")
for i in range(1, 4):
    res("retail-prod", "rg-eshop-prod", "microsoft.web/serverfarms", f"asp-eshop-web-{i}", "app",
        "Azure App Service", "Compute", "app", app="eshop", rtype_name="App Service plan")
res("retail-prod", "rg-eshop-prod", "microsoft.network/publicipaddresses", "pip-eshop-fd", "bw",
    "Bandwidth", "Networking", "bw", app="eshop", rtype_name="Public IP address")
res("retail-prod", "rg-eshop-ai", "microsoft.cognitiveservices/accounts", "aoai-eshop-assistant", "aoai_mini",
    "Azure OpenAI", "AI and Machine Learning", "mini_in", app="eshop-assistant", start=date(2026, 7, 1),
    rtype_name="Azure OpenAI")
res("retail-prod", "rg-bi", "microsoft.fabric/capacities", "fcretailbi", "fabric",
    "Microsoft Fabric", "Analytics", "fabric", qty=8, app="retail-bi", rtype_name="Fabric capacity")
for i in range(1, 4):
    res("retail-dev", "rg-eshop-dev", VM, f"vm-eshop-dev-{i:02}", "vm", "Virtual Machines", "Compute", "d4s",
        app="eshop", pattern="workhours", rtype_name="Virtual machine", tags="full" if i < 3 else "partial")
# Contoso Logistics
for i in range(1, 4):
    res("logistics-prod", "rg-tms-prod", VM, f"vm-tms-sql-{i:02}", "vm", "Virtual Machines", "Compute",
        "e8s_win" if i == 1 else "e8s", app="tms", rtype_name="Virtual machine",
        end=END if i < 3 else date(2026, 8, 17), extra={"ri": "e8s", "ahb": False if i == 1 else None})
res("logistics-prod", "rg-tms-prod", "microsoft.dbforpostgresql/flexibleservers", "pg-tms-prod", "pg",
    "Azure Database for PostgreSQL", "Databases", "pg", app="tms", rtype_name="Azure Database for PostgreSQL flexible server")
for i in range(1, 5):
    res("logistics-dev", "rg-tms-dev", VM, f"vm-tms-dev-{i:02}", "vm", "Virtual Machines", "Compute", "d4s",
        app="tms", rtype_name="Virtual machine", tags="badcase" if i > 2 else "full")
for i in range(1, 4):
    res("logistics-dev", "rg-tms-dev", "microsoft.compute/disks", f"disk-tms-old-{i:02}", "disk", "Storage",
        "Storage", "disk_p30", app="tms", rtype_name="Disk", tags="none", extra={"orphan": True})
# Contoso Data Platform
res("dataplatform-prod", "rg-fabric-prod", "microsoft.fabric/capacities", "fcdataprod", "fabric",
    "Microsoft Fabric", "Analytics", "fabric", qty=64, app="data-platform", rtype_name="Fabric capacity",
    extra={"ri_from": date(2026, 9, 1), "overage": [date(2026, 10, d) for d in (6, 7, 8, 27, 28)]})
res("dataplatform-prod", "rg-fabric-prod", "microsoft.fabric/capacities", "fcdataprod", "onelake",
    "Microsoft Fabric", "Storage", "onelake", qty=9000, app="data-platform", rtype_name="Fabric capacity")
res("dataplatform-dev", "rg-fabric-dev", "microsoft.fabric/capacities", "fcdatadev", "fabric",
    "Microsoft Fabric", "Analytics", "fabric", qty=16, app="data-platform", rtype_name="Fabric capacity")
res("dataplatform-prod", "rg-dbx-prod", "microsoft.databricks/workspaces", "dbw-lakehouse-prod", "dbx",
    "Azure Databricks", "Analytics", "dbx_jobs", app="lakehouse", rtype_name="Azure Databricks Service",
    end=date(2026, 10, 31))
res("dataplatform-prod", "rg-dbx-prod", "microsoft.databricks/workspaces", "dbw-lakehouse-prod", "dbxsql",
    "Azure Databricks", "Analytics", "dbx_sql", app="lakehouse", rtype_name="Azure Databricks Service",
    end=date(2026, 10, 31))
res("dataplatform-prod", "rg-datalake-prod", "microsoft.storage/storageaccounts", "stcontosodlprod", "blob",
    "Storage", "Storage", "blob", qty=62000, app="datalake", rtype_name="Storage account")
# Contoso AI Lab
res("ailab", "rg-genai-poc", "microsoft.cognitiveservices/accounts", "aoai-ailab", "aoai_4o",
    "Azure OpenAI", "AI and Machine Learning", "gpt4o_in", app="genai-poc", rtype_name="Azure OpenAI", tags="partial")
res("ailab", "rg-gpu-finetune", VM, "vm-a100-finetune", "vm", "Virtual Machines", "Compute", "nc",
    app="finetune", start=date(2026, 9, 8), end=date(2026, 10, 2), rtype_name="Virtual machine", tags="partial")
# Shared
res("shared-connectivity", "rg-monitoring", "microsoft.operationalinsights/workspaces", "log-contoso-central",
    "loga", "Log Analytics", "Management and Governance", "loga", app="monitoring", rtype_name="Log Analytics workspace")


def hours_on(pattern, d):
    if pattern == "workhours":
        return 12 if d.weekday() < 5 else 0
    return 24


def tags_json(t):
    return json.dumps(t, ensure_ascii=False) if t else "{}"


rows = []


def add(r, d, *, meter, consumed, cunit, list_price, pqty=None, punit=None, block=1, charge_cat="Usage",
        charge_freq="Usage-Based", pricing_cat="Standard", cd=None, cd_status=None, billed=None,
        effective=None, desc=None, sku_meter_cat=None, sku_sub=None, contracted_disc=EA_DISCOUNT,
        no_resource=False, unit_desc=None):
    pqty = consumed / block if pqty is None else pqty
    list_cost = pqty * list_price
    contracted_price = list_price * (1 - contracted_disc)
    contracted_cost = pqty * contracted_price
    billed = contracted_cost if billed is None else billed
    effective = contracted_cost if effective is None else effective
    spolka, env = SUBS[r["sub"]]
    ps = datetime(d.year, d.month, 1, tzinfo=timezone.utc)
    pe = (ps + timedelta(days=32)).replace(day=1)
    rid = None if no_resource else r["rid"]
    rows.append({
        "BilledCost": round(billed, 6),
        "BillingAccountId": BILLING_ACCOUNT_ID,
        "BillingAccountName": BILLING_ACCOUNT_NAME,
        "BillingAccountType": "Billing Account",
        "BillingCurrency": CUR,
        "BillingPeriodEnd": pe,
        "BillingPeriodStart": ps,
        "ChargeCategory": charge_cat,
        "ChargeClass": None,
        "ChargeDescription": desc or meter,
        "ChargeFrequency": charge_freq,
        "ChargePeriodEnd": datetime(d.year, d.month, d.day, tzinfo=timezone.utc) + timedelta(days=1),
        "ChargePeriodStart": datetime(d.year, d.month, d.day, tzinfo=timezone.utc),
        "CommitmentDiscountCategory": None if not cd else "Usage",
        "CommitmentDiscountId": None if not cd else cd["id"],
        "CommitmentDiscountName": None if not cd else cd["name"],
        "CommitmentDiscountStatus": cd_status,
        "CommitmentDiscountType": None if not cd else "Reservation",
        "ConsumedQuantity": round(consumed, 6) if charge_cat == "Usage" else None,
        "ConsumedUnit": cunit if charge_cat == "Usage" else None,
        "ContractedCost": round(contracted_cost, 6),
        "ContractedUnitPrice": round(contracted_price, 8),
        "EffectiveCost": round(effective, 6),
        "InvoiceIssuerName": "Microsoft",
        "ListCost": round(list_cost, 6),
        "ListUnitPrice": round(list_price, 8),
        "PricingCategory": pricing_cat,
        "PricingQuantity": round(pqty, 6),
        "PricingUnit": punit or cunit,
        "ProviderName": "Microsoft",
        "PublisherName": "Microsoft",
        "RegionId": r["region"],
        "RegionName": {"westeurope": "West Europe", "swedencentral": "Sweden Central"}.get(r["region"], r["region"]),
        "ResourceId": rid,
        "ResourceName": None if no_resource else r["name"].split("/")[-1],
        "ResourceType": None if no_resource else r["rtype_name"],
        "ServiceCategory": r["category"],
        "ServiceName": r["service"],
        "SkuId": None,
        "SkuPriceId": None,
        "SubAccountId": None if no_resource else f"/subscriptions/{SUB_ID[r['sub']]}",
        "SubAccountName": None if no_resource else f"sub-contoso-{r['sub']}",
        "SubAccountType": None if no_resource else "Subscription",
        "Tags": "{}" if no_resource else tags_json(r["tags"]),
        "x_BilledCostInUsd": round(billed * EUR_USD, 6),
        "x_BillingExchangeRate": EUR_USD,
        "x_BillingProfileId": "90000001",
        "x_BillingProfileName": BILLING_ACCOUNT_NAME,
        "x_ContractedCostInUsd": round(contracted_cost * EUR_USD, 6),
        "x_CostCenter": None,
        "x_EffectiveCostInUsd": round(effective * EUR_USD, 6),
        "x_EffectiveUnitPrice": round(effective / pqty, 8) if pqty else 0.0,
        "x_ListCostInUsd": round(list_cost * EUR_USD, 6),
        "x_PricingBlockSize": float(block),
        "x_PricingCurrency": CUR,
        "x_PricingUnitDescription": unit_desc or cunit,
        "x_PublisherCategory": "Cloud Provider",
        "x_ResourceGroupName": None if no_resource else r["rg"],
        "x_ResourceType": None if no_resource else r["rp_type"].rsplit("/", 0)[0],
        "x_SkuDescription": desc or meter,
        "x_SkuDetails": None,
        "x_SkuMeterCategory": sku_meter_cat or r["service"],
        "x_SkuMeterName": meter,
        "x_SkuMeterSubcategory": sku_sub,
        "x_SkuRegion": "EU West",
        "x_SkuTerm": 12 if cd and charge_cat == "Purchase" else None,
        "x_SourceName": "Synthetic",
        "x_SourceProvider": "Microsoft",
        "x_SourceType": "Synthetic",
        "x_SourceVersion": "1.0",
    })


def noise(scale=0.05):
    return float(max(0.0, RNG.normal(1.0, scale)))


RI = {
    "d4s": {"id": "/providers/microsoft.capacity/reservationorders/" + gid("ro", "d4s") + "/reservations/" + gid("r", "d4s"),
            "name": "RI-D4sv5-eshop-1Y", "qty": 4, "hourly": P["d4s_ri"]["retailPrice"] / 8760,
            "sub": "retail-prod", "from": START},
    "e8s": {"id": "/providers/microsoft.capacity/reservationorders/" + gid("ro", "e8s") + "/reservations/" + gid("r", "e8s"),
            "name": "RI-E8sv5-tms-1Y", "qty": 3, "hourly": P["e8s_ri"]["retailPrice"] / 8760,
            "sub": "logistics-prod", "from": START},
    "fabric": {"id": "/providers/microsoft.capacity/reservationorders/" + gid("ro", "fab") + "/reservations/" + gid("r", "fab"),
               "name": "RI-Fabric-64CU-1Y", "qty": 64, "hourly": FABRIC_RI_HOURLY, "sub": "dataplatform-prod",
               "from": date(2026, 9, 1)},
}
ri_used = {}  # (ri, day) -> zużyte jednostko-godziny

days = [START + timedelta(days=i) for i in range((END - START).days + 1)]
for d in days:
    month_idx = (d.year - 2026) * 12 + d.month - 5  # 0 = maj
    weekend = d.weekday() >= 5
    for r in resources:
        if not (r["start"] <= d <= r["end"]):
            continue
        k, pk = r["kind"], r["pkey"]
        if k == "vm":
            h = hours_on(r["pattern"], d)
            if h == 0:
                continue
            p = P[pk]
            ri = RI.get(r["extra"].get("ri") or "")
            meter = p["meterName"]
            desc = f"{p['productName']} - {p['skuName']} - EU West"
            if ri and d >= ri["from"] and ri_used.get((r["extra"]["ri"], d), 0) < ri["qty"] * 24 - 0.1:
                ri_used[(r["extra"]["ri"], d)] = ri_used.get((r["extra"]["ri"], d), 0) + h
                lp = P["e8s"]["retailPrice"] if pk == "e8s_win" else p["retailPrice"]
                add(r, d, meter=meter, consumed=h, cunit="Hours", punit="Hours", list_price=lp,
                    pricing_cat="Committed", cd=ri, cd_status="Used", billed=0.0, effective=h * ri["hourly"],
                    desc=desc, sku_meter_cat="Virtual Machines", sku_sub=p["productName"])
                if pk == "e8s_win":  # licencja Windows poza rezerwacją, brak Azure Hybrid Benefit
                    win = P["e8s_win"]["retailPrice"] - P["e8s"]["retailPrice"]
                    add(r, d, meter=meter + " - Windows license", consumed=h, cunit="Hours", list_price=win,
                        desc=desc + " (Windows Server license)", sku_meter_cat="Virtual Machines Licenses",
                        sku_sub="Windows Server")
            else:
                add(r, d, meter=meter, consumed=h * noise(0.0), cunit="Hours", list_price=p["retailPrice"],
                    desc=desc, sku_meter_cat="Virtual Machines", sku_sub=p["productName"])
        elif k == "sqldb":
            add(r, d, meter="vCore", consumed=24, cunit="Hours", list_price=P[pk]["retailPrice"],
                desc="SQL Database General Purpose - Compute Gen5 - 8 vCore", sku_meter_cat="SQL Database",
                sku_sub="Single/Elastic Pool General Purpose - Compute Gen5")
        elif k == "pg":
            add(r, d, meter="vCore", consumed=24, cunit="Hours", list_price=P[pk]["retailPrice"],
                desc="Azure Database for PostgreSQL Flexible Server - D4ds v5", sku_meter_cat="Azure Database for PostgreSQL")
        elif k == "app":
            add(r, d, meter="P1 v3 App", consumed=24, cunit="Hours", list_price=P[pk]["retailPrice"],
                desc="Azure App Service Premium v3 Plan - Linux - P1 v3", sku_meter_cat="Azure App Service")
        elif k == "bw":
            gb = 900 * (1 + 0.04 * month_idx) * (1.35 if weekend else 1.0) * noise(0.12)
            add(r, d, meter="Standard Data Transfer Out", consumed=gb, cunit="GB", list_price=P[pk]["retailPrice"],
                desc="Bandwidth - Data Transfer Out - Internet", sku_meter_cat="Bandwidth")
        elif k == "disk":
            add(r, d, meter="P30 LRS Disk", consumed=1 / 30, cunit="Disks/Month", list_price=P[pk]["retailPrice"],
                pqty=1 / 30, desc="Premium SSD Managed Disks - P30 LRS (nieprzypięty dysk)", sku_meter_cat="Storage",
                sku_sub="Premium SSD Managed Disks")
        elif k == "blob":
            gb = r["qty"] * (1 + 0.035 * month_idx + 0.001 * d.day)
            add(r, d, meter="Hot LRS Data Stored", consumed=gb / 30, cunit="GB/Month", list_price=P[pk]["retailPrice"],
                desc="General Block Blob v2 - Hot LRS Data Stored", sku_meter_cat="Storage", sku_sub="General Block Blob v2")
        elif k == "loga":
            gb = 38 * noise(0.08)
            if date(2026, 10, 13) <= d <= date(2026, 10, 24):  # debug logging włączony w TMS, wysyłany do workspace centralnego
                gb += 95 * noise(0.1)
            add(r, d, meter="Analytics Logs Data Ingestion", consumed=gb, cunit="GB", list_price=P[pk]["retailPrice"],
                desc="Log Analytics - Analytics Logs Data Ingestion", sku_meter_cat="Log Analytics")
        elif k == "dbx":
            dbu = 520 * (0.55 if weekend else 1.0) * noise(0.15) * (1 - 0.08 * max(0, month_idx - 3))
            add(r, d, meter="Premium Jobs Compute DBU", consumed=dbu, cunit="DBU", list_price=P[pk]["retailPrice"],
                desc="Azure Databricks - Premium Jobs Compute", sku_meter_cat="Azure Databricks")
        elif k == "dbxsql":
            dbu = 140 * (0.3 if weekend else 1.0) * noise(0.2)
            add(r, d, meter="Premium Serverless SQL DBU", consumed=dbu, cunit="DBU", list_price=P[pk]["retailPrice"],
                desc="Azure Databricks - Premium Serverless SQL", sku_meter_cat="Azure Databricks")
        elif k in ("aoai_mini", "aoai_4o"):
            growth = (1.25 if k == "aoai_mini" else 1.15) ** max(0, month_idx - (2 if k == "aoai_mini" else 0))
            base_in = (380_000_000 if k == "aoai_mini" else 12_000_000) * growth * (0.7 if weekend else 1) * noise(0.15)
            pin, pout = (P["mini_in"], P["mini_out"]) if k == "aoai_mini" else (P["gpt4o_in"], P["gpt4o_out"])
            for p, toks in ((pin, base_in), (pout, base_in * 0.18)):
                add(r, d, meter=p["meterName"], consumed=toks, cunit="Tokens", punit="1000 Tokens", block=1000,
                    list_price=p["retailPrice"], desc=f"Azure OpenAI - {p['meterName']}", unit_desc="1K",
                    sku_meter_cat="Foundry Models", sku_sub="Azure OpenAI")
        elif k == "onelake":
            gb = r["qty"] * (1 + 0.06 * month_idx)
            add(r, d, meter="OneLake Storage Hot Data Stored", consumed=gb / 30, cunit="GB/Month",
                list_price=P[pk]["retailPrice"], desc="OneLake Storage Hot Data Stored", sku_meter_cat="Microsoft Fabric",
                sku_sub="OneLake", contracted_disc=0.0)
        elif k == "fabric":
            cu_h = r["qty"] * 24
            ri = RI["fabric"] if r["name"] == "fcdataprod" and d >= RI["fabric"]["from"] else None
            for meter, share in FABRIC_METERS.items():
                s = share * (1 + RNG.normal(0, 0.05))
                q = cu_h * s
                if ri:
                    add(r, d, meter=meter, consumed=q, cunit="CU Hours", list_price=FABRIC_CU, pricing_cat="Committed",
                        cd=ri, cd_status="Used", billed=0.0, effective=q * ri["hourly"], contracted_disc=0.0,
                        desc=f"Microsoft Fabric - {meter}", sku_meter_cat="Microsoft Fabric", sku_sub="Fabric Capacity")
                else:
                    add(r, d, meter=meter, consumed=q, cunit="CU Hours", list_price=FABRIC_CU, contracted_disc=0.0,
                        desc=f"Microsoft Fabric - {meter}", sku_meter_cat="Microsoft Fabric", sku_sub="Fabric Capacity")
            if d in r["extra"].get("overage", []):
                q = r["qty"] * 24 * 0.22 * noise(0.2)
                add(r, d, meter="Capacity Overage Capacity Usage CU", consumed=q, cunit="CU Hours",
                    list_price=P["fabric_overage"]["retailPrice"], contracted_disc=0.0,
                    desc="Microsoft Fabric - Capacity Overage (3x PAYG)", sku_meter_cat="Microsoft Fabric",
                    sku_sub="Fabric Capacity")

# Rezerwacje: zakup miesięczny (Purchase) oraz niewykorzystana część (Unused)
anchor = {"d4s": "vm-eshop-app-01", "e8s": "vm-tms-sql-02", "fabric": "fcdataprod"}
for key, ri in RI.items():
    r = next(x for x in resources if x["name"] == anchor[key])
    unit_h = 24
    yearly = {"d4s": P["d4s_ri"], "e8s": P["e8s_ri"], "fabric": P["fabric_ri"]}[key]["retailPrice"]
    for d in days:
        if d < ri["from"]:
            continue
        if d.day == 1:
            fee = yearly * ri["qty"] / 12
            add(r, d, meter="Reservation - " + ri["name"], consumed=0, cunit="Units", pqty=ri["qty"],
                list_price=yearly / 12, charge_cat="Purchase", charge_freq="Recurring", pricing_cat="Committed",
                cd=ri, billed=fee, effective=0.0, contracted_disc=0.0, desc=f"Reservation purchase {ri['name']} (monthly)",
                sku_meter_cat="Reservation", no_resource=False)
        if key == "fabric":
            continue
        used = ri_used.get((key, d), 0)
        unused_h = ri["qty"] * unit_h - used
        if unused_h > 0.5:
            lp = P["d4s" if key == "d4s" else "e8s"]["retailPrice"]
            add(r, d, meter="Unused reservation " + ri["name"], consumed=unused_h, cunit="Hours", list_price=lp,
                pricing_cat="Committed", cd=ri, cd_status="Unused", billed=0.0, effective=unused_h * ri["hourly"],
                desc=f"Unused reservation hours {ri['name']}", sku_meter_cat="Virtual Machines", no_resource=True)

df = pd.DataFrame(rows)
for c in ("BillingPeriodEnd", "BillingPeriodStart", "ChargePeriodEnd", "ChargePeriodStart"):
    df[c] = pd.to_datetime(df[c], utc=True)
df["x_SkuTerm"] = df["x_SkuTerm"].astype("float64")
str_cols = [c for c in df.columns if df[c].dtype == object]
for c in str_cols:
    df[c] = df[c].astype("string")

print("wierszy:", len(df))
print(df.groupby(df["ChargePeriodStart"].dt.strftime("%Y-%m"))[["BilledCost", "EffectiveCost", "ListCost"]].sum().round(0))

ing_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
base = OUT / "focus_syntetyczne"
if base.exists():
    for f in base.rglob("*.parquet"):
        f.unlink()
for (y, m), part in df.groupby([df["BillingPeriodStart"].dt.year, df["BillingPeriodStart"].dt.month]):
    p = base / f"{y:04}" / f"{m:02}" / "contoso-polska"
    p.mkdir(parents=True, exist_ok=True)
    part.to_parquet(p / f"{ing_id}__part0.parquet", index=False, compression="snappy")
df.to_parquet(OUT / "focus_syntetyczne_all.parquet", index=False, compression="snappy")
df.head(300).to_csv(OUT / "focus_syntetyczne_probka.csv", index=False)

pd.DataFrame(SPOLKI, columns=["CostCenter", "Spolka", "WlascicielBudzetu", "BudzetMiesiecznyEUR"]).to_csv(
    OUT / "dim_spolki.csv", index=False)
subs = pd.DataFrame([{"SubAccountId": f"/subscriptions/{SUB_ID[k]}", "SubAccountName": f"sub-contoso-{k}",
                      "Spolka": v[0], "CostCenter": CC[v[0]], "Srodowisko": v[1]} for k, v in SUBS.items()])
subs.to_csv(OUT / "dim_subskrypcje.csv", index=False)
print("zapisano do", OUT)
