"""Konfiguracja wdrożenia z zmiennych środowiskowych.

Repozytorium nie zawiera identyfikatorów żadnego konkretnego tenanta. Przed uruchomieniem
skryptów wdrożeniowych ustaw zmienne opisane w README (sekcja o konfiguracji).
Bez zmiennych skrypty działają tylko w trybie --offline, a w generowanych plikach
zostają placeholdery w nawiasach ostrych.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DANE = os.path.join(HERE, "..", "dane")
FTK = os.path.join(HERE, "ftk-v15")

WS = os.environ.get("FABRIC_WORKSPACE_ID", "<FABRIC_WORKSPACE_ID>")
WS_NAME = os.environ.get("FABRIC_WORKSPACE_NAME", "<FABRIC_WORKSPACE_NAME>")
LH = os.environ.get("FABRIC_LAKEHOUSE_ID", "<FABRIC_LAKEHOUSE_ID>")
EVENTHOUSE_URI = os.environ.get("EVENTHOUSE_QUERY_URI", "<EVENTHOUSE_QUERY_URI>")
SUBSCRIPTION = os.environ.get("AZURE_SUBSCRIPTION_ID") or None
HUB_STORAGE = os.environ.get("FINOPS_HUB_STORAGE_ACCOUNT", "<FINOPS_HUB_STORAGE_ACCOUNT>")


def require(*names):
    """Przerywa skrypt, gdy brakuje którejś z wymaganych zmiennych środowiskowych."""
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise SystemExit("Brak zmiennych środowiskowych: " + ", ".join(missing) + ". Zobacz README.")
