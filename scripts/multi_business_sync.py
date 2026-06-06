# /// script
# requires-python = ">=3.11"
# dependencies = ["python-dotenv"]
# ///
"""Run plaid_sync.py once per Wave business while keeping core logic upstream-aligned.

Uses existing env vars:
- PLAID_ACCESS_TOKENS: JSON array (preferred) or legacy colon-delimited entries.
- WAVE_BUSINESS_ID: default business id for unmapped accounts.
- PLAID_ACCOUNT_BUSINESS_IDS: optional map account_id_or_name:business_id.
- KEYWORDS_FILES_BY_BUSINESS: optional map business_id:path_to_keywords_file.

All CLI args are forwarded to plaid_sync.py unchanged.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv


def parse_mapping_env(var_name: str) -> dict[str, str]:
    raw = os.environ.get(var_name, "").strip()
    if not raw:
        return {}

    parsed: dict[str, str] = {}
    for entry in raw.split(","):
        item = entry.strip()
        if not item:
            continue
        if ":" not in item:
            print(f"warning: skipping malformed {var_name} entry: {entry}", file=sys.stderr)
            continue
        key, value = item.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            print(f"warning: skipping malformed {var_name} entry: {entry}", file=sys.stderr)
            continue
        parsed[key] = value
    return parsed


def parse_accounts(raw: str) -> list[dict[str, str]]:
    raw = raw.strip()
    if not raw:
        return []

    if raw.startswith("["):
        try:
            entries = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"error: PLAID_ACCESS_TOKENS JSON parse failed: {exc}", file=sys.stderr)
            return []

        accounts: list[dict[str, str]] = []
        for entry in entries:
            if not all(k in entry for k in ("name", "token", "wave_account", "type")):
                print(
                    f"warning: skipping JSON entry missing required fields: {list(entry.keys())}",
                    file=sys.stderr,
                )
                continue
            accounts.append(
                {
                    "name": str(entry["name"]),
                    "token": str(entry["token"]),
                    "wave_account": str(entry["wave_account"]),
                    "type": str(entry["type"]),
                    "account_id": str(entry.get("account_id", "")),
                }
            )
        return accounts

    accounts = []
    for entry in raw.split(","):
        parts = entry.strip().split(":")
        if len(parts) < 4:
            print(f"warning: skipping malformed account entry: {entry}", file=sys.stderr)
            continue
        name, token, rest = parts[0], parts[1], parts[2:]
        account_id = ""
        if rest[-1] in ("checking", "credit_card"):
            acct_type, wave_account = rest[-1], ":".join(rest[:-1])
        elif len(rest) >= 2 and rest[-2] in ("checking", "credit_card"):
            acct_type, account_id, wave_account = rest[-2], rest[-1], ":".join(rest[:-2])
        else:
            acct_type, wave_account = rest[-1], ":".join(rest[:-1])
        accounts.append(
            {
                "name": name,
                "token": token,
                "wave_account": wave_account,
                "type": acct_type,
                "account_id": account_id,
            }
        )
    return accounts


def resolve_business_id(
    acct_cfg: dict[str, str], account_business_map: dict[str, str], default_business_id: str
) -> str:
    account_id = acct_cfg.get("account_id", "")
    if account_id and account_id in account_business_map:
        return account_business_map[account_id]
    if acct_cfg["name"] in account_business_map:
        return account_business_map[acct_cfg["name"]]
    return default_business_id


def compact_accounts_json(accounts: list[dict[str, str]]) -> str:
    payload = []
    for acct in accounts:
        item = {
            "name": acct["name"],
            "token": acct["token"],
            "wave_account": acct["wave_account"],
            "type": acct["type"],
        }
        if acct.get("account_id"):
            item["account_id"] = acct["account_id"]
        payload.append(item)
    return json.dumps(payload, separators=(",", ":"))


def run_once(args: list[str], env: dict[str, str]) -> int:
    cmd = ["uv", "run", "plaid_sync.py", *args]
    proc = subprocess.run(cmd, env=env)
    return proc.returncode


def main() -> int:
    load_dotenv()

    passthrough_args = sys.argv[1:]
    one_shot_flags = {"--add-bank", "--reauth", "--help", "-h"}
    if any(flag in passthrough_args for flag in one_shot_flags):
        return run_once(passthrough_args, os.environ.copy())

    raw_accounts = os.environ.get("PLAID_ACCESS_TOKENS", "")
    accounts_cfg = parse_accounts(raw_accounts)
    if not accounts_cfg:
        print("error: no valid accounts configured in PLAID_ACCESS_TOKENS", file=sys.stderr)
        return 1

    default_business_id = os.environ.get("WAVE_BUSINESS_ID", "")
    account_business_map = parse_mapping_env("PLAID_ACCOUNT_BUSINESS_IDS")
    keywords_file_map = parse_mapping_env("KEYWORDS_FILES_BY_BUSINESS")

    accounts_by_business: dict[str, list[dict[str, str]]] = defaultdict(list)
    for acct_cfg in accounts_cfg:
        biz_id = resolve_business_id(acct_cfg, account_business_map, default_business_id)
        accounts_by_business[biz_id].append(acct_cfg)

    if not account_business_map and default_business_id:
        print(
            "note: PLAID_ACCOUNT_BUSINESS_IDS is not set; all accounts route to WAVE_BUSINESS_ID",
            file=sys.stderr,
        )

    if len(accounts_by_business) == 1 and account_business_map:
        only_biz = next(iter(accounts_by_business))
        print(
            f"note: account routing resolved to one business ({only_biz or 'auto-detect'}); "
            "verify PLAID_ACCOUNT_BUSINESS_IDS keys match account_id or account name exactly",
            file=sys.stderr,
        )

    if not accounts_by_business:
        print("error: no accounts to sync after routing", file=sys.stderr)
        return 1

    order = sorted(accounts_by_business.keys(), key=lambda x: (x == "", x))
    exit_code = 0

    for biz_id in order:
        scoped_env = os.environ.copy()
        scoped_env["PLAID_ACCESS_TOKENS"] = compact_accounts_json(accounts_by_business[biz_id])

        if biz_id:
            scoped_env["WAVE_BUSINESS_ID"] = biz_id
        else:
            scoped_env.pop("WAVE_BUSINESS_ID", None)

        if biz_id and biz_id in keywords_file_map:
            scoped_env["KEYWORDS_FILE"] = keywords_file_map[biz_id]

        label = biz_id or "(auto-detect default business)"
        print(f"\n{'='*60}\nBusiness scope: {label} | Accounts: {len(accounts_by_business[biz_id])}\n{'='*60}")
        rc = run_once(passthrough_args, scoped_env)
        if rc != 0:
            exit_code = rc if exit_code == 0 else exit_code

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
