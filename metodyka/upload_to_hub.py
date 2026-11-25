"""Wysyła syntetyczne pliki FOCUS do kontenera ingestion w storage FinOps hub.

Układ: ingestion/Costs/<yyyy>/<mm>/contoso-polska/<plik>.parquet. Po plikach parquet każdy
folder dostaje pusty manifest.json, bo na ten plik reaguje trigger ingestion_ManifestAdded
w Data Factory huba i dopiero wtedy uruchamia się ładowanie do Data Explorer / Eventhouse.

Wymaga zmiennej FINOPS_HUB_STORAGE_ACCOUNT (nazwa konta storage z wdrożenia huba), roli
Storage Blob Data Contributor na tym koncie oraz sieciowego dostępu do jego endpointu DFS.

Ten skrypt nie był uruchamiany w obecnej postaci. Sprawdź wynik w pipeline'ach Data Factory
huba (ingestion_ExecuteETL) i w tabeli Costs w bazie Hub.

Użycie: python upload_to_hub.py [--dry-run]
"""
import os
import sys

import requests

from config import DANE, HUB_STORAGE, require
from fabric_api import token

CONTAINER = "ingestion"


def put(base, path, data: bytes):
    h = {"Authorization": f"Bearer {token('https://storage.azure.com')}", "x-ms-version": "2023-11-03"}
    url = f"{base}/{path}"
    requests.put(url + "?resource=file", headers=h).raise_for_status()
    if data:
        requests.patch(url + "?action=append&position=0", headers=h, data=data).raise_for_status()
    requests.patch(url + f"?action=flush&position={len(data)}", headers=h).raise_for_status()


def main():
    dry = "--dry-run" in sys.argv
    if not dry:
        require("FINOPS_HUB_STORAGE_ACCOUNT")
    base = f"https://{HUB_STORAGE}.dfs.core.windows.net/{CONTAINER}"
    src = os.path.join(DANE, "focus_syntetyczne")
    folders = []
    for root, _, files in os.walk(src):
        rel_dir = os.path.relpath(root, src).replace("\\", "/")
        parquet = [f for f in files if f.endswith(".parquet")]
        for f in parquet:
            target = f"Costs/{rel_dir}/{f}"
            print(("[dry-run] " if dry else "") + target)
            if not dry:
                put(base, target, open(os.path.join(root, f), "rb").read())
        if parquet:
            folders.append(rel_dir)
    for rel_dir in folders:
        target = f"Costs/{rel_dir}/manifest.json"
        print(("[dry-run] " if dry else "") + target)
        if not dry:
            put(base, target, b"{}")


if __name__ == "__main__":
    main()
