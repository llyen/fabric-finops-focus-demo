r"""Buduje deck otwierający sesję techniczną (deck\FinOps_Fabric_otwarcie.pptx)."""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Emu, Inches, Pt

OUT = Path(__file__).resolve().parent.parent / "deck" / "FinOps_Fabric_otwarcie.pptx"
FONT = "Segoe UI"
NAVY = RGBColor(0x0B, 0x2A, 0x4A)
BLUE = RGBColor(0x00, 0x78, 0xD4)
TEAL = RGBColor(0x00, 0x8C, 0x7A)
ORANGE = RGBColor(0xD8, 0x6A, 0x00)
GREY = RGBColor(0x5A, 0x5A, 0x5A)
LIGHT = RGBColor(0xF2, 0xF5, 0xF9)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


def text(slide, x, y, w, h, lines, size=18, color=GREY, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for i, ln in enumerate([lines] if isinstance(lines, str) else lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if isinstance(ln, tuple):
            ln, opts = ln
        else:
            opts = {}
        r = p.add_run()
        r.text = ln
        r.font.name = FONT
        r.font.size = Pt(opts.get("size", size))
        r.font.bold = opts.get("bold", bold)
        r.font.color.rgb = opts.get("color", color)
        p.space_after = Pt(opts.get("after", 6))
    return tb


def box(slide, x, y, w, h, fill, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line:
        s.line.color.rgb = line
        s.line.width = Pt(1.25)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = 0.08
    return s


def label(shape, lines, size=14, color=WHITE, bold=False, align=PP_ALIGN.CENTER):
    tf = shape.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for m in ("margin_left", "margin_right"):
        setattr(tf, m, Inches(0.1))
    for i, ln in enumerate([lines] if isinstance(lines, str) else lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = ln
        r.font.name = FONT
        r.font.size = Pt(size if i == 0 else size - 3)
        r.font.bold = bold and i == 0
        r.font.color.rgb = color


def slide(title, kicker=None, notes=None):
    s = prs.slides.add_slide(BLANK)
    box(s, 0, 0, 0.18, 7.5, BLUE, shape=MSO_SHAPE.RECTANGLE)
    if kicker:
        text(s, 0.6, 0.35, 12, 0.4, kicker, size=13, color=BLUE, bold=True)
    text(s, 0.6, 0.65, 12.2, 0.9, title, size=30, color=NAVY, bold=True)
    text(s, 0.6, 7.0, 12.2, 0.35, "FinOps w Azure i Microsoft Fabric  |  sesja techniczna 45 min", size=10, color=GREY)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


def table(s, x, y, w, rows, col_w, size=13, head=NAVY, row_h=0.42):
    t = s.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w),
                           Inches(row_h * len(rows))).table
    for j, cw in enumerate(col_w):
        t.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            c = t.cell(i, j)
            c.text = val
            c.fill.solid()
            c.fill.fore_color.rgb = head if i == 0 else (LIGHT if i % 2 else WHITE)
            c.margin_left = c.margin_right = Inches(0.08)
            for p in c.text_frame.paragraphs:
                for r in p.runs:
                    r.font.name = FONT
                    r.font.size = Pt(size)
                    r.font.bold = i == 0
                    r.font.color.rgb = WHITE if i == 0 else GREY
    return t


# 1. Tytuł
s = prs.slides.add_slide(BLANK)
box(s, 0, 0, 13.333, 7.5, NAVY, shape=MSO_SHAPE.RECTANGLE)
box(s, 0.8, 2.35, 0.12, 2.2, BLUE, shape=MSO_SHAPE.RECTANGLE)
text(s, 1.15, 2.2, 11, 1.2, "FinOps w Azure i Microsoft Fabric", size=44, color=WHITE, bold=True)
text(s, 1.15, 3.35, 11, 0.8, "Od eksportu FOCUS do agenta, który odpowiada na pytania o koszty", size=22,
     color=RGBColor(0xC8, 0xD8, 0xEA))
text(s, 1.15, 4.3, 11, 0.5, "Sesja techniczna, 45 minut", size=16,
     color=RGBColor(0xC8, 0xD8, 0xEA))
s.notes_slide.notes_text_frame.text = (
    "Zapowiedź: mniej slajdów, więcej demo. Dane firmy Contoso Polska są syntetyczne. "
    "Jeśli do huba podłączono własny eksport FOCUS, można go pokazać obok nich.")

# 2. Agenda
s = slide("Plan na 45 minut", "Agenda", "Pilnuj, żeby demo zaczęło się najpóźniej w 14. minucie.")
table(s, 0.6, 1.7, 12.1, [
    ["Czas", "Blok", "Co zobaczymy"],
    ["0:00", "Po co FinOps i gdzie jest Fabric", "Trzy fazy FinOps, model kosztów Fabric"],
    ["0:05", "FOCUS", "Wspólny schemat danych kosztowych, eksport w Cost Management"],
    ["0:10", "Architektura demo", "FinOps hub na Fabric Eventhouse, Lakehouse, Direct Lake"],
    ["0:14", "Demo 1, hub i KQL", "Tagi, anomalie, rezerwacje, Effective Savings Rate"],
    ["0:22", "Demo 2, raport Power BI", "Budżety spółek, showback, alokacja"],
    ["0:30", "Demo 3, Data Agent", "Pytania o koszty w języku naturalnym"],
    ["0:36", "FinOps dla samego Fabric", "Capacity Metrics, Chargeback, surge protection"],
    ["0:41", "Pytania", ""],
], [1.2, 4.1, 6.8], size=15, row_h=0.55)

# 3. Fazy FinOps
s = slide("FinOps to pętla, nie projekt", "FinOps Framework",
          "Fazy według FinOps Framework (FinOps Foundation), opisane też w Microsoft Learn: "
          "learn.microsoft.com/cloud-computing/finops/framework/finops-framework. "
          "Na każdej karcie dolna linijka mówi, gdzie ta faza pojawi się w demo.")
cards = [
    ("Inform", BLUE, ["Widoczność i alokacja", "Kto ile wydaje, na co, w porównaniu z budżetem",
                      "W demo: showback spółek, tagi CostCenter"]),
    ("Optimize", TEAL, ["Stawki i zużycie", "Rezerwacje, savings plan, AHB, sprzątanie nieużywanych zasobów",
                        "W demo: wykorzystanie RI, ESR, osierocone dyski"]),
    ("Operate", ORANGE, ["Ciągłe usprawnianie", "Anomalie, polityki, automatyzacja, kultura odpowiedzialności",
                         "W demo: wykrywanie anomalii w KQL, Data Agent"]),
]
for i, (name, col, body) in enumerate(cards):
    x = 0.6 + i * 4.15
    box(s, x, 1.8, 3.9, 0.9, col)
    label(s.shapes[-1], name, size=24, bold=True)
    b = box(s, x, 2.75, 3.9, 2.9, LIGHT)
    text(s, x + 0.25, 2.95, 3.4, 3.3, [(body[0], {"bold": True, "color": NAVY, "size": 18, "after": 12}),
                                         (body[1], {"after": 18}),
                                         (body[2], {"color": col, "size": 15})], size=16)

# 4. FOCUS
s = slide("Jeden schemat dla kosztów z każdej chmury", "FOCUS, czyli FinOps Open Cost and Usage Specification",
          "Eksport w Cost Management ma typ FocusCost. "
          "FinOps hub v15 udostępnia funkcje w wersjach schematu, w demo używamy Costs(). "
          "Aktualna wersja specyfikacji na focus.finops.org (sprawdzone 15.11.2026): 1.4. "
          "Źródło: learn.microsoft.com/cloud-computing/finops/focus/what-is-focus")
text(s, 0.6, 1.7, 5.2, 4.8, [
    ("Otwarta specyfikacja FinOps Foundation. Te same nazwy kolumn i definicje u różnych dostawców "
     "chmury i SaaS.", {"after": 16}),
    ("W Azure dostępna jako typ eksportu w Cost Management, dziennie, do parquet na Storage.", {"after": 16}),
    ("Jeden plik łączy koszt rzeczywisty i zamortyzowany, więc znika klasyczny dylemat "
     "„actual czy amortized”.", {"after": 16}),
    ("Demo w całości stoi na kolumnach FOCUS, łącznie z danymi syntetycznymi.", {"color": BLUE}),
], size=17)
table(s, 6.2, 1.75, 6.5, [
    ["Kolumna", "Co mówi"],
    ["BilledCost", "Kwota na fakturze"],
    ["EffectiveCost", "Koszt po rabatach i amortyzacji zobowiązań"],
    ["ListCost", "Koszt według cennika publicznego"],
    ["ChargeCategory", "Usage, Purchase, Tax, Credit, Adjustment"],
    ["CommitmentDiscountStatus", "Used albo Unused, czyli wykorzystanie rezerwacji"],
    ["ServiceCategory", "Kategoria usługi niezależna od dostawcy"],
    ["Tags", "Tagi zasobu, podstawa alokacji"],
], [2.6, 3.9], size=14, row_h=0.55)

# 5. Model kosztów Fabric
s = slide("Za co płacimy w Microsoft Fabric", "Fabric z perspektywy FinOps",
          "Źródła: learn.microsoft.com/fabric/onelake/onelake-consumption (storage per GB, także przy pauzie), "
          "learn.microsoft.com/fabric/enterprise/azure-billing (rezerwacja na osobnym mierniku), "
          "learn.microsoft.com/azure/cost-management-billing/reservations/fabric-capacity. "
          "Dni z przekroczeniem rezerwacji w danych Contoso są syntetyczne.")
cols = [
    ("Pojemność (CU)", BLUE, ["Pay-as-you-go za czas działania pojemności F SKU",
                              "Pauza zatrzymuje naliczanie za moc obliczeniową",
                              "Rezerwacja na 1 lub 3 lata, rozliczana na osobnym mierniku",
                              "Zużycie ponad rezerwację wraca do stawki PAYG"]),
    ("OneLake storage", TEAL, ["Płatny za GB według stawki PAYG",
                               "Nie zużywa CU",
                               "Naliczany także wtedy, gdy pojemność jest wstrzymana"]),
    ("Podział w organizacji", ORANGE, ["Jedna pojemność, wiele zespołów i workspace'ów",
                                       "Capacity Metrics pokazuje, kto zużywa CU",
                                       "Chargeback app dzieli koszt pojemności",
                                       "Surge protection chroni przed jednym zachłannym zadaniem"]),
]
for i, (name, col, body) in enumerate(cols):
    x = 0.6 + i * 4.15
    box(s, x, 1.8, 3.9, 0.75, col)
    label(s.shapes[-1], name, size=20, bold=True)
    box(s, x, 2.6, 3.9, 3.9, LIGHT)
    text(s, x + 0.25, 2.8, 3.45, 3.6, [(b, {"after": 14}) for b in body], size=16)

# 6. Architektura
s = slide("Architektura demo", "Elementy demo",
          "Hub to FinOps toolkit v15 w trybie Fabric Real-Time Intelligence. Dane syntetyczne trafiają "
          "do kontenera ingestion huba. Eksport z Cost Management jest opcjonalny.")


def node(x, y, w, h, lines, fill, fg=WHITE):
    b = box(s, x, y, w, h, fill)
    label(b, lines, size=15, color=fg, bold=True)
    return b


def arrow(a, b, txt=None):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, a.left + a.width, a.top + a.height // 2,
                               b.left, b.top + b.height // 2)
    c.line.color.rgb = GREY
    c.line.width = Pt(2)
    c.line._get_or_add_ln().append(
        __import__("lxml.etree", fromlist=["etree"]).fromstring(
            '<a:tailEnd xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" type="triangle"/>'))
    if txt:
        mx = (a.left + a.width + b.left) / 2
        my = min(a.top + a.height // 2, b.top + b.height // 2)
        text(s, Emu(int(mx)).inches - 0.9, Emu(int(my)).inches - 0.45, 1.8, 0.4, txt, size=11,
             align=PP_ALIGN.CENTER)


cm = node(0.6, 1.9, 2.4, 1.1, ["Cost Management", "eksport FOCUS, opcjonalnie"], BLUE)
syn = node(0.6, 4.3, 2.4, 1.1, ["Generator FOCUS", "dane syntetyczne Contoso"], ORANGE)
hub = node(3.7, 1.9, 2.4, 1.1, ["FinOps hub v15", "Storage i Data Factory"], NAVY)
eh = node(6.8, 1.9, 2.6, 1.1, ["Fabric Eventhouse", "KQL, dashboard i raporty"], TEAL)
lh = node(3.7, 4.3, 2.4, 1.1, ["Lakehouse", "lh_finops, Delta"], TEAL)
sm = node(6.8, 4.3, 2.6, 1.1, ["Model semantyczny", "Direct Lake"], TEAL)
rp = node(10.1, 3.65, 2.6, 0.95, ["Raport Power BI", "budżet, alokacja"], NAVY)
da = node(10.1, 4.95, 2.6, 0.95, ["Data Agent", "pytania po polsku"], NAVY)
arrow(cm, hub, "parquet")
arrow(hub, eh, "ADF ETL")
arrow(syn, lh)
arrow(lh, sm)
arrow(sm, rp)
arrow(sm, da)
c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, syn.left + syn.width // 2, syn.top, hub.left + hub.width // 4,
                           hub.top + hub.height)
c.line.color.rgb = GREY
c.line.width = Pt(1.5)
c.line.dash_style = 4
text(s, 0.3, 3.4, 2.0, 0.6, "do kontenera ingestion", size=11, align=PP_ALIGN.RIGHT)
text(s, 0.6, 6.1, 12.1, 0.6, "Pomarańczowy to dane syntetyczne, niebieski to opcjonalny własny eksport FOCUS. "
     "W Hub oba źródła rozróżnia kolumna x_SourceName.", size=14, color=NAVY)

# 7. Contoso Polska
s = slide("Contoso Polska, fikcyjna grupa z prawdziwymi problemami", "Dane syntetyczne w demo",
          "Ceny jednostkowe z Azure Retail Prices API (westeurope, EUR). Wolumeny, rabat EA 5%, tagi, budżety "
          "i zdarzenia są wymyślone na potrzeby demo. Liczby z modelu semantycznego.")
text(s, 0.6, 1.7, 5.6, 4.9, [
    ("Pięć spółek, osiem subskrypcji, maj do połowy listopada 2026, około 212 tys. EUR kosztu efektywnego.",
     {"after": 16, "color": NAVY, "size": 18}),
    ("Każda spółka ma miesięczny budżet i swój CostCenter. Część zasobów taguje się źle albo wcale.",
     {"after": 16}),
    ("Pytania, które zadamy danym:", {"after": 8, "color": BLUE}),
    ("Która spółka przekroczyła budżet i dlaczego?", {"after": 4}),
    ("Ile kosztu nie da się przypisać?", {"after": 4}),
    ("Czy rezerwacje się zwracają?", {"after": 4}),
    ("Co się zmieniło i kiedy?", {"after": 4}),
], size=17)
table(s, 6.6, 1.75, 6.1, [
    ["Kiedy", "Co się stało"],
    ["lipiec", "Start asystenta Azure OpenAI w Retail"],
    ["17 sierpnia", "Wyłączona maszyna objęta rezerwacją"],
    ["1 września", "Zakup rezerwacji Fabric 64 CU"],
    ["wrzesień", "Maszyna A100 w AI Lab bez tagu CostCenter"],
    ["13 do 24 października", "Logowanie debug do Log Analytics"],
    ["31 października", "Wyłączenie Databricks po migracji do Fabric"],
    ["cały okres", "Osierocone dyski bez tagów"],
], [2.3, 3.8], size=14, row_h=0.55)

# 8. Przejście do demo
s = slide("Przechodzimy do demo", "Za chwilę",
          "Przed przejściem: karta z KQL w Eventhouse, raport i Data Agent otwarte w przeglądarce.")
steps = [("1", "Hub i KQL", "Gotowe raporty Microsoftu z FinOps toolkit, potem własne KQL. Tagi, anomalie, ESR.", BLUE),
         ("2", "Raport Power BI", "Budżet w sumie wygląda dobrze. Budżet we wrześniu już nie.", TEAL),
         ("3", "Data Agent", "To samo pytanie zadane po polsku, z podglądem wygenerowanego DAX.", ORANGE)]
for i, (n, t, d, col) in enumerate(steps):
    y = 1.85 + i * 1.5
    c = box(s, 0.8, y, 1.1, 1.1, col, shape=MSO_SHAPE.OVAL)
    label(c, n, size=32, bold=True)
    text(s, 2.2, y + 0.02, 10.3, 0.5, t, size=24, color=NAVY, bold=True)
    text(s, 2.2, y + 0.55, 10.3, 0.5, d, size=17)

OUT.parent.mkdir(exist_ok=True)
prs.save(OUT)
print(OUT)
