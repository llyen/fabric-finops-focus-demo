"""Przygotowanie tabel Lakehouse lh_finops pod model Direct Lake.

Direct Lake nie obsluguje kolumn obliczanych, wiec tagi, daty i alokacja CostCenter
sa wyliczane tutaj. Wszystkie dane sa SYNTETYCZNE (Contoso Polska).
"""
import json, os, shutil, subprocess, time
import pandas as pd
import requests
from config import WS, LH, DANE, require
from fabric_api import call
from onelake import put

require("FABRIC_WORKSPACE_ID", "FABRIC_LAKEHOUSE_ID")

df = pd.read_parquet(os.path.join(DANE, "focus_syntetyczne_all.parquet"))
subs = pd.read_csv(os.path.join(DANE, "dim_subskrypcje.csv"))


def tag_info(s):
    t = json.loads(s) if s else {}
    low = {k.lower(): v for k, v in t.items()}
    exact = t.get("CostCenter")
    if not t:
        status = "Brak tagow"
    elif exact:
        status = "Poprawny"
    elif "costcenter" in low:
        status = "Bledna wielkosc liter"
    else:
        status = "Brak CostCenter"
    return exact, low.get("costcenter"), low.get("env"), low.get("app"), status


info = df.Tags.map(tag_info)
df["TagCostCenter"] = info.map(lambda x: x[0])
df["TagCostCenterDowolnaWielkosc"] = info.map(lambda x: x[1])
df["TagEnv"] = info.map(lambda x: x[2])
df["TagApp"] = info.map(lambda x: x[3])
df["StatusTagowania"] = info.map(lambda x: x[4])
cc_sub = df.SubAccountId.map(subs.set_index("SubAccountId").CostCenter)
df["CostCenterAlokacja"] = df.TagCostCenterDowolnaWielkosc.str.upper().fillna(cc_sub).fillna("Nieprzypisane")
df["ZrodloAlokacji"] = df.TagCostCenterDowolnaWielkosc.notna().map({True: "Tag", False: "Subskrypcja"})
df.loc[df.CostCenterAlokacja == "Nieprzypisane", "ZrodloAlokacji"] = "Brak"
# Load Table API nie obsluguje timestampNtz, wiec daty zostaja w UTC
df["ChargeDate"] = df.ChargePeriodStart.dt.normalize()
df["Oszczednosci"] = df.ListCost - df.EffectiveCost

dates = pd.DataFrame({"Data": pd.date_range("2026-05-01", "2026-11-30", freq="D", tz="UTC")})
dates["Rok"] = dates.Data.dt.year
dates["MiesiacNr"] = dates.Data.dt.month
dates["Miesiac"] = dates.Data.dt.strftime("%Y-%m")
dates["DzienTygodnia"] = dates.Data.dt.dayofweek + 1
dates["CzyWeekend"] = dates.DzienTygodnia >= 6

spolki = pd.read_csv(os.path.join(DANE, "dim_spolki.csv"))
spolki = pd.concat([spolki, pd.DataFrame([{"CostCenter": "Nieprzypisane", "Spolka": "Nieprzypisane",
                                            "WlascicielBudzetu": None, "BudzetMiesiecznyEUR": 0}])])

out = os.path.join(DANE, "lakehouse")
os.makedirs(out, exist_ok=True)
tables = {"focus_costs": df, "dim_data": dates, "dim_spolki": spolki, "dim_subskrypcje": subs}
# Load Table zapisuje daty jako timestamp_ntz i potem odrzuca Overwrite, wiec tabela jest usuwana
tok = json.loads(subprocess.check_output([shutil.which("az"), "account", "get-access-token",
                                          "--resource", "https://storage.azure.com"]))["accessToken"]
for name, t in tables.items():
    p = os.path.join(out, f"{name}.parquet")
    t.to_parquet(p, index=False, coerce_timestamps="us", allow_truncated_timestamps=True)
    put(f"raw/{name}.parquet", open(p, "rb").read())
    requests.delete(f"https://onelake.dfs.fabric.microsoft.com/{WS}/{LH}/Tables/{name}?recursive=true",
                    headers={"Authorization": "Bearer " + tok})
    time.sleep(15)
    r = call("POST", f"/workspaces/{WS}/lakehouses/{LH}/tables/{name}/load",
             {"relativePath": f"Files/raw/{name}.parquet", "pathType": "File", "mode": "Overwrite",
              "formatOptions": {"format": "Parquet"}})
    print(name, len(t), (r or {}).get("status"))
print(df.groupby("StatusTagowania").EffectiveCost.sum().round(0).to_dict())
