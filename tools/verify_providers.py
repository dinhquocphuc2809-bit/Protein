"""Read-only checks. Credential values and provider error bodies never enter reports."""

from __future__ import annotations

import concurrent.futures
import datetime as dt
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT.parent


def records(provider: str) -> list[str]:
    return [
        line.strip()
        for line in (INPUT / f"api-key-{provider}.txt").read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def get(url: str, headers: dict[str, str]) -> tuple[int, dict]:
    response = requests.get(url, headers=headers, timeout=(10, 30), allow_redirects=False)
    try:
        body = response.json()
    except ValueError:
        body = {}
    return response.status_code, body if isinstance(body, dict) else {}


def probe(task: tuple[str, int, str]) -> dict:
    provider, index, key = task
    result = {"provider": provider, "record": index, "checked_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    try:
        bearer = {"Authorization": f"Bearer {key}"}
        if provider == "tunelio":
            status, body = get("https://tunelio.dev/credits", bearer)
            result.update(status=status)
            if status == 200:
                result.update(credits=body.get("credits"), plan=body.get("plan"))
        elif provider == "gemini":
            status, body = get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000", {"x-goog-api-key": key})
            result.update(status=status)
            if status == 200:
                result["models"] = [m["name"] for m in body.get("models", [])]
                result["has_more_pages"] = bool(body.get("nextPageToken"))
        elif provider == "deepseek":
            status, body = get("https://api.deepseek.com/models", bearer)
            result.update(status=status)
            if status == 200:
                result["models"] = [m["id"] for m in body.get("data", [])]
            status, body = get("https://api.deepseek.com/user/balance", bearer)
            result["balance_status"] = status
            if status == 200:
                result.update(is_available=body.get("is_available"), balances=body.get("balance_infos"))
        elif provider == "apify":
            status, _ = get("https://api.apify.com/v2/users/me", bearer)
            result["status"] = status
            status, body = get("https://api.apify.com/v2/users/me/limits", bearer)
            result["limits_status"] = status
            if status == 200:
                data = body.get("data", {})
                result["limits"] = data.get("limits")
                result["current"] = data.get("current")
        elif provider == "deepgram":
            headers = {"Authorization": f"Token {key}"}
            status, _ = get("https://api.deepgram.com/v1/auth/token", headers)
            result["status"] = status
            status, body = get("https://api.deepgram.com/v1/projects", headers)
            result["projects_status"] = status
            balances = []
            for project in body.get("projects", []) if status == 200 else []:
                code, data = get(f"https://api.deepgram.com/v1/projects/{project['project_id']}/balances", headers)
                balances.append({"status": code, "balances": [
                    {k: b[k] for k in ("amount", "units", "purchase_source") if k in b}
                    for b in data.get("balances", [])
                ]})
            result["balances"] = balances
    except requests.RequestException as error:
        result["error"] = type(error).__name__
    return result


def main() -> None:
    tasks = [(provider, n, key) for provider in ("gemini", "deepseek", "apify", "deepgram", "tunelio")
             for n, key in enumerate(records(provider), 1)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(probe, tasks))
    output = ROOT / "research" / "provider-verification.json"
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    for provider in ("gemini", "deepseek", "apify", "deepgram", "tunelio"):
        rows = [row for row in results if row["provider"] == provider]
        counts = {}
        for row in rows:
            status = str(row.get("status", row.get("error", "unknown")))
            counts[status] = counts.get(status, 0) + 1
        print(provider, counts)


if __name__ == "__main__":
    main()
