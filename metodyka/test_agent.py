"""Zadaje pytania opublikowanemu Data Agentowi przez endpoint zgodny z OpenAI Assistants.

Użycie: python test_agent.py "pytanie 1" "pytanie 2"
"""
import sys
import time
import uuid

import requests

from fabric_api import token, find_item
from config import WS, require

AGENT = "DA_FinOps_Contoso"
API_VERSION = "2024-05-01-preview"


def ask(base, question):
    h = {"Authorization": f"Bearer {token()}", "Content-Type": "application/json",
         "ActivityId": str(uuid.uuid4())}
    q = {"api-version": API_VERSION}
    a = requests.post(f"{base}/assistants", params=q, headers=h, json={"model": "not used"}).json()
    t = requests.post(f"{base}/threads", params=q, headers=h, json={}).json()
    requests.post(f"{base}/threads/{t['id']}/messages", params=q, headers=h,
                  json={"role": "user", "content": question}).raise_for_status()
    run = requests.post(f"{base}/threads/{t['id']}/runs", params=q, headers=h,
                        json={"assistant_id": a["id"]}).json()
    for _ in range(90):
        if run.get("status") in ("completed", "failed", "cancelled", "expired"):
            break
        time.sleep(3)
        run = requests.get(f"{base}/threads/{t['id']}/runs/{run['id']}", params=q, headers=h).json()
    msgs = requests.get(f"{base}/threads/{t['id']}/messages", params={**q, "order": "asc"}, headers=h).json()
    answer = [c["text"]["value"] for m in msgs.get("data", []) if m["role"] == "assistant"
              for c in m["content"] if c["type"] == "text"]
    requests.delete(f"{base}/threads/{t['id']}", params=q, headers=h)
    return run.get("status"), "\n".join(answer) or str(run.get("last_error"))


def main():
    require("FABRIC_WORKSPACE_ID")
    agent = find_item(WS, AGENT, "DataAgent")
    base = f"https://api.fabric.microsoft.com/v1/workspaces/{WS}/dataagents/{agent['id']}/aiassistant/openai"
    for qn in sys.argv[1:]:
        st, ans = ask(base, qn)
        print(f"\n### {qn}\n[{st}]\n{ans}")


if __name__ == "__main__":
    main()
