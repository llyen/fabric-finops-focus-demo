"""Zapis plików do sekcji Files lakehouse w OneLake (ADLS Gen2 DFS API)."""
import requests
from config import WS, LH
from fabric_api import token

DFS = f"https://onelake.dfs.fabric.microsoft.com/{WS}/{LH}/Files"


def put(path, data: bytes):
    h = {"Authorization": f"Bearer {token('https://storage.azure.com')}"}
    url = f"{DFS}/{path}"
    requests.put(url + "?resource=file", headers=h).raise_for_status()
    if data:
        requests.patch(url + "?action=append&position=0", headers=h, data=data).raise_for_status()
    requests.patch(url + f"?action=flush&position={len(data)}", headers=h).raise_for_status()


def delete_dir(path):
    h = {"Authorization": f"Bearer {token('https://storage.azure.com')}"}
    requests.delete(f"{DFS}/{path}?recursive=true", headers=h)
