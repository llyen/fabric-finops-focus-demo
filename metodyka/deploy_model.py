"""Model semantyczny Direct Lake nad lh_finops (dane SYNTETYCZNE Contoso Polska).

Uzycie: python deploy_model.py            (tworzy model, gdy go nie ma, inaczej updateDefinition)
       python deploy_model.py --offline  (tylko zapis TMDL do model/, bez wdrozenia)
"""
import base64, json, sys, textwrap
from config import WS, LH, require

NAME = "SM_FinOps_Contoso"
EXPR = "DL_lh_finops"


def tm(s):
    """Wciecia po 4 spacje zamieniane na taby (TMDL)."""
    lines = textwrap.dedent(s).strip("\n").split("\n")
    out = []
    for l in lines:
        n = len(l) - len(l.lstrip(" "))
        out.append("\t" * (n // 4) + l.lstrip(" "))
    return "\n".join(out) + "\n"


def col(name, src, dtype, hidden=False, summarize="none", fmt=None, desc=None, extra=""):
    s = ""
    if desc:
        s += f"    /// {desc}\n"
    q = f"'{name}'" if any(c in name for c in " .=:'") or not name.isascii() else name
    s += f"    column {q}\n        dataType: {dtype}\n"
    if hidden:
        s += "        isHidden\n"
    if fmt:
        s += f"        formatString: {fmt}\n"
    s += f"        summarizeBy: {summarize}\n        sourceColumn: {src}\n"
    for e in extra.split("|"):
        if e:
            s += f"        {e}\n"
    return s + "\n"


def meas(name, dax, fmt, desc, folder=None):
    s = f"    /// {desc}\n"
    if "\n" in dax:
        body = "\n".join("            " + l for l in dax.strip().split("\n"))
        s += f"    measure '{name}' = ```\n{body}\n            ```\n"
    else:
        s += f"    measure '{name}' = {dax}\n"
    s += f"        formatString: {fmt}\n"
    if folder:
        s += f"        displayFolder: {folder}\n"
    return s + "\n"


def part(table, entity):
    return (f"    partition '{table}' = entity\n        mode: directLake\n        source\n"
            f"            entityName: {entity}\n            expressionSource: {EXPR}\n")


EUR = '#,##0" €"'
PCT = "0.0%"

koszty = "/// Wiersze kosztow w formacie FOCUS 1.0 (dzien x zasob x miernik). Dane syntetyczne Contoso Polska.\ntable Koszty\n\n"
koszty += meas("Koszt efektywny", "SUM(Koszty[EffectiveCost])", EUR,
               "Suma EffectiveCost z FOCUS: koszt po rabatach z amortyzacja rezerwacji. Glowna miara do showback i chargeback.", "Koszty")
koszty += meas("Koszt fakturowany", "SUM(Koszty[BilledCost])", EUR,
               "Suma BilledCost z FOCUS: kwota na fakturze, zakupy rezerwacji widoczne w dniu zakupu.", "Koszty")
koszty += meas("Koszt cennikowy", "SUM(Koszty[ListCost])", EUR,
               "Suma ListCost z FOCUS: koszt wedlug cen katalogowych bez rabatow.", "Koszty")
koszty += meas("Oszczednosci", "[Koszt cennikowy] - [Koszt efektywny]", EUR,
               "Roznica miedzy kosztem cennikowym a efektywnym, czyli efekt rabatow i rezerwacji.", "Optymalizacja")
koszty += meas("Stopa oszczednosci", "DIVIDE([Oszczednosci], [Koszt cennikowy])", PCT,
               "Oszczednosci jako odsetek kosztu cennikowego (Effective Savings Rate).", "Optymalizacja")
koszty += meas("Koszt bez poprawnego tagu", 'CALCULATE([Koszt efektywny], Koszty[Status tagowania] <> "Poprawny")', EUR,
               "Koszt efektywny wierszy, w ktorych brak tagu CostCenter albo tag ma bledna wielkosc liter.", "Alokacja")
koszty += meas("Udzial kosztu bez poprawnego tagu", "DIVIDE([Koszt bez poprawnego tagu], [Koszt efektywny])", PCT,
               "Odsetek kosztu efektywnego bez poprawnego tagu CostCenter. KPI zgodnosci tagowania.", "Alokacja")
koszty += meas("Koszt niewykorzystanych rezerwacji",
               'CALCULATE([Koszt efektywny], Koszty[CommitmentDiscountStatus] = "Unused")', EUR,
               "Koszt efektywny godzin rezerwacji, ktore nie zostaly wykorzystane (CommitmentDiscountStatus = Unused).", "Optymalizacja")
koszty += meas("Wykorzystanie rezerwacji", """
DIVIDE(
    CALCULATE([Koszt efektywny], Koszty[CommitmentDiscountStatus] = "Used"),
    CALCULATE([Koszt efektywny], NOT ISBLANK(Koszty[CommitmentDiscountStatus]))
)""", PCT, "Udzial wykorzystanej czesci rezerwacji w calym koszcie rezerwacji (Used wobec Used plus Unused).", "Optymalizacja")
koszty += meas("Koszt poprzedni miesiac",
               "CALCULATE([Koszt efektywny], DATEADD(Kalendarz[Data], -1, MONTH))", EUR,
               "Koszt efektywny w miesiacu poprzedzajacym okres z kontekstu filtra.", "Trend")
koszty += meas("Zmiana m/m", """
VAR Biezacy = [Koszt efektywny]
VAR Poprzedni = [Koszt poprzedni miesiac]
RETURN
    DIVIDE(Biezacy - Poprzedni, Poprzedni)""", PCT, "Zmiana kosztu efektywnego miesiac do miesiaca.", "Trend")
koszty += meas("Liczba zasobow", "DISTINCTCOUNT(Koszty[ResourceId])", "#,##0",
               "Liczba unikalnych zasobow (ResourceId) z kosztem w okresie.", "Koszty")

for name, src, dt, kw in [
    ("ChargeDate", "ChargeDate", "dateTime", dict(hidden=True, fmt="yyyy-mm-dd", desc="Klucz do Kalendarz (poczatek dnia naliczenia)")),
    ("CostCenterAlokacja", "CostCenterAlokacja", "string", dict(hidden=True, desc="Klucz do Spolki po alokacji (tag, potem subskrypcja)")),
    ("SubAccountId", "SubAccountId", "string", dict(hidden=True, desc="Klucz do Subskrypcje")),
    ("ResourceId", "ResourceId", "string", dict(hidden=True, desc="Identyfikator zasobu Azure")),
    ("EffectiveCost", "EffectiveCost", "double", dict(hidden=True, summarize="sum")),
    ("BilledCost", "BilledCost", "double", dict(hidden=True, summarize="sum")),
    ("ListCost", "ListCost", "double", dict(hidden=True, summarize="sum")),
    ("ServiceName", "ServiceName", "string", dict(desc="Usluga wedlug FOCUS, np. Virtual Machines, Azure OpenAI")),
    ("ServiceCategory", "ServiceCategory", "string", dict(desc="Kategoria uslugi wedlug FOCUS, np. Compute, Analytics")),
    ("ResourceName", "ResourceName", "string", dict(desc="Nazwa zasobu Azure")),
    ("ResourceType", "ResourceType", "string", dict(desc="Typ zasobu")),
    ("x_ResourceGroupName", "x_ResourceGroupName", "string", dict(desc="Grupa zasobow (rozszerzenie Microsoft)")),
    ("RegionName", "RegionName", "string", dict(desc="Region Azure")),
    ("ChargeCategory", "ChargeCategory", "string", dict(desc="Usage albo Purchase")),
    ("PricingCategory", "PricingCategory", "string", dict(desc="Standard albo Committed (rezerwacja)")),
    ("CommitmentDiscountType", "CommitmentDiscountType", "string", dict(desc="Typ zobowiazania, tu Reservation")),
    ("CommitmentDiscountName", "CommitmentDiscountName", "string", dict(desc="Nazwa rezerwacji")),
    ("CommitmentDiscountStatus", "CommitmentDiscountStatus", "string", dict(desc="Used albo Unused dla wierszy rezerwacji")),
    ("x_SkuMeterCategory", "x_SkuMeterCategory", "string", dict(desc="Kategoria miernika")),
    ("x_SkuMeterName", "x_SkuMeterName", "string", dict(desc="Nazwa miernika, np. gpt-4o input tokens")),
    ("PricingUnit", "PricingUnit", "string", dict(desc="Jednostka cenowa")),
    ("Tags", "Tags", "string", dict(desc="Surowe tagi zasobu w JSON")),
    ("Tag CostCenter", "TagCostCenter", "string", dict(desc="Wartosc tagu CostCenter zapisanego dokladnie w tej wielkosci liter")),
    ("Tag Env", "TagEnv", "string", dict(desc="Wartosc tagu env (bez wzgledu na wielkosc liter klucza)")),
    ("Tag App", "TagApp", "string", dict(desc="Wartosc tagu app")),
    ("Status tagowania", "StatusTagowania", "string", dict(desc="Poprawny, Bledna wielkosc liter, Brak CostCenter albo Brak tagow")),
    ("Zrodlo alokacji", "ZrodloAlokacji", "string", dict(desc="Skad przypisano CostCenter: Tag, Subskrypcja albo Brak")),
]:
    koszty += col(name, src, dt, **kw)
koszty += part("Koszty", "focus_costs")

kal = "/// Kalendarz dzienny od 2026-05-01 do 2026-11-30.\ntable Kalendarz\n    dataCategory: Time\n\n"
kal += col("Data", "Data", "dateTime", fmt="yyyy-mm-dd", extra="isKey", desc="Dzien")
kal += col("Rok", "Rok", "int64", fmt="0", desc="Rok kalendarzowy")
kal += col("MiesiacNr", "MiesiacNr", "int64", hidden=True, fmt="0")
kal += col("Miesiac", "Miesiac", "string", desc="Miesiac w formacie RRRR-MM")
kal += col("Dzien tygodnia", "DzienTygodnia", "int64", fmt="0", desc="1 poniedzialek, 7 niedziela")
kal += col("Czy weekend", "CzyWeekend", "boolean", desc="Prawda dla soboty i niedzieli")
kal += "    hierarchy 'Rok miesiac dzien'\n\n        level Rok\n            column: Rok\n\n        level Miesiac\n            column: Miesiac\n\n        level Data\n            column: Data\n\n"
kal += part("Kalendarz", "dim_data")

sp = "/// Spolki grupy Contoso Polska z centrami kosztow i budzetami miesiecznymi (dane syntetyczne).\ntable Spolki\n\n"
sp += meas("Budzet", """
SUMX(
    CALCULATETABLE(VALUES(Kalendarz[Miesiac]), Koszty),
    CALCULATE(SUM(Spolki[BudzetMiesiecznyEUR]))
)""", EUR, "Budzet miesieczny spolek pomnozony przez liczbe miesiecy z kosztami w kontekscie filtra.", "Budzet")
sp += meas("Wykonanie budzetu", "DIVIDE([Koszt efektywny], [Budzet])", PCT,
           "Koszt efektywny jako odsetek budzetu. Powyzej 100% oznacza przekroczenie.", "Budzet")
sp += meas("Odchylenie od budzetu", "[Koszt efektywny] - [Budzet]", EUR,
           "Koszt efektywny minus budzet. Wartosc dodatnia oznacza przekroczenie.", "Budzet")
sp += col("CostCenter", "CostCenter", "string", desc="Centrum kosztow, klucz alokacji")
sp += col("Spolka", "Spolka", "string", desc="Nazwa spolki")
sp += col("Wlasciciel budzetu", "WlascicielBudzetu", "string", desc="Adres osoby odpowiedzialnej za budzet")
sp += col("BudzetMiesiecznyEUR", "BudzetMiesiecznyEUR", "int64", hidden=True, summarize="sum", fmt="0")
sp += part("Spolki", "dim_spolki")

sub = "/// Subskrypcje Azure z przypisaniem do spolki i srodowiska (dane syntetyczne).\ntable Subskrypcje\n\n"
sub += col("SubAccountId", "SubAccountId", "string", hidden=True)
sub += col("Subskrypcja", "SubAccountName", "string", desc="Nazwa subskrypcji")
sub += col("Spolka wlasciciel subskrypcji", "Spolka", "string", desc="Spolka, do ktorej nalezy subskrypcja")
sub += col("CostCenter subskrypcji", "CostCenter", "string", hidden=True)
sub += col("Srodowisko", "Srodowisko", "string", desc="prod, dev albo shared")
sub += part("Subskrypcje", "dim_subskrypcje")

rels = """
relationship Koszty_Kalendarz
    fromColumn: Koszty.ChargeDate
    toColumn: Kalendarz.Data

relationship Koszty_Spolki
    fromColumn: Koszty.CostCenterAlokacja
    toColumn: Spolki.CostCenter

relationship Koszty_Subskrypcje
    fromColumn: Koszty.SubAccountId
    toColumn: Subskrypcje.SubAccountId
"""

expr = f"""
expression {EXPR} =
        let
            Source = AzureStorage.DataLake("https://onelake.dfs.fabric.microsoft.com/{WS}/{LH}", [HierarchicalNavigation=true])
        in
            Source
"""

model = """
model Model
    culture: pl-PL
    defaultPowerBIDataSourceVersion: powerBI_V3
    discourageImplicitMeasures
    sourceQueryCulture: pl-PL

ref table Koszty
ref table Kalendarz
ref table Spolki
ref table Subskrypcje
"""

parts = {
    "definition.pbism": json.dumps({"version": "4.2", "settings": {"qnaEnabled": True}}),
    "definition/database.tmdl": "database\n\tcompatibilityLevel: 1604\n\tcompatibilityMode: powerBI\n",
    "definition/model.tmdl": tm(model),
    "definition/expressions.tmdl": tm(expr),
    "definition/relationships.tmdl": tm(rels),
    "definition/tables/Koszty.tmdl": tm(koszty),
    "definition/tables/Kalendarz.tmdl": tm(kal),
    "definition/tables/Spolki.tmdl": tm(sp),
    "definition/tables/Subskrypcje.tmdl": tm(sub),
}

if __name__ == "__main__":
    import os
    outdir = os.path.join(os.path.dirname(__file__), "..", "model", NAME + ".SemanticModel")
    for p, c in parts.items():
        fp = os.path.join(outdir, *p.split("/"))
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        open(fp, "w", encoding="utf-8", newline="\n").write(c)
    if "--offline" in sys.argv:
        print("zapisano", outdir)
        sys.exit(0)
    require("FABRIC_WORKSPACE_ID", "FABRIC_LAKEHOUSE_ID")
    from fabric_api import call, find_item
    payload = {"parts": [{"path": p, "payload": base64.b64encode(c.encode()).decode(), "payloadType": "InlineBase64"}
                         for p, c in parts.items()]}
    existing = find_item(WS, NAME, "SemanticModel")
    if existing:
        call("POST", f"/workspaces/{WS}/semanticModels/{existing['id']}/updateDefinition", {"definition": payload})
        print("updated", existing["id"])
    else:
        call("POST", f"/workspaces/{WS}/semanticModels", {"displayName": NAME, "definition": payload})
        print("created", (find_item(WS, NAME, "SemanticModel") or {}).get("id"))
