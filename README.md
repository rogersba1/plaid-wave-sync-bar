# plaid-wave-sync

Automatically sync bank transactions from [Plaid](https://plaid.com) → [Wave](https://www.waveapps.com) accounting. No Wave Pro subscription necessary.

- **Keyword-based categorization** — auto-generated from your previous year's general ledger
- **Deduplication** — safe to re-run anytime (uses Plaid transaction IDs)
- **Credit card support** — handles both checking and CC accounts
- **Invoice matching** — auto-marks invoices as paid when deposits match
- **GitHub Actions ready** — runs daily on a schedule, zero infrastructure

---

## Setup (5 minutes)

### Step 1 → Fork this repo

[![Fork this repo](https://img.shields.io/badge/1-Fork_this_repo_→-181717?style=for-the-badge&logo=github)](../../fork)

### Step 2 → Open in Codespaces

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/jeffreylsoffer/plaid-wave-sync?quickstart=1)

> **Important:** Open the Codespace from YOUR fork, not this repo.

The setup script runs automatically and walks you through everything:
- Creates your Plaid account & activates trial (10 free bank connections)
- Connects your bank accounts via Plaid Hosted Link
- Shows your Wave accounts and matches them to your banks
- Generates keyword mappings from your Wave general ledger CSV
- Saves all secrets to your repo
- Enables the workflow and triggers a test run

Once setup completes, close the Codespace — everything runs automatically from there.

---

## Usage

```bash
# Preview what would sync
uv run plaid_sync.py --dry-run --days 30

# Sync for real
uv run plaid_sync.py --days 30

# Weekly reconciliation check
uv run plaid_sync.py --reconcile --days 7

# Validate your keyword mappings
uv run plaid_sync.py --dump-accounts

# Multi-business run (routes accounts per business)
uv run scripts/multi_business_sync.py --dry-run --days 30
```

## How It Works

```
Plaid (bank)              keywords.json           Wave (accounting)
     │                         │                        │
     │  fetch transactions     │  categorize            │  create entries
     ├────────────────────────►├───────────────────────►│
     │                         │                        │
     │  positive = expense     │  keyword match → acct  │  deduped by
     │  negative = income      │  no match → fallback   │  transaction_id
```

- **Checking accounts**: Plaid positive = money out (expense), negative = money in (income)
- **Credit cards**: Plaid positive = charge (expense), negative = payment/refund
- **Invoices**: Income deposits are auto-matched to open invoices by customer name + amount
- **Duplicates**: Silently skipped via `externalId` — safe to re-run anytime

## Commands

| Flag | Description |
|------|-------------|
| `--days N` | Sync last N days (default: 30) |
| `--dry-run` | Preview without writing to Wave |
| `--reconcile` | Compare Plaid totals for the period |
| `--dump-accounts` | Show Wave accounts + validate keywords |
| `--add-bank` | Connect a new bank via Plaid Hosted Link |
| `--debug` | Verbose logging |

## Multi-Business Setup

Keep `plaid_sync.py` close to upstream for core sync logic, and use the multi-business wrapper to fan out runs by business.

Run with:

```bash
uv run scripts/multi_business_sync.py --days 30
```

The wrapper runs `plaid_sync.py` once per business scope.

Use these env vars:

- `WAVE_BUSINESS_ID` = default business id (used when an account is not explicitly mapped)
- `PLAID_ACCOUNT_BUSINESS_IDS` = map each Plaid account to a Wave business id
- `KEYWORDS_FILES_BY_BUSINESS` = use a separate keywords json file per business id
- `KEYWORDS_FILE` = optional default keyword file for the default business (fallback: `keywords.json`)

Format examples:

```bash
# Optional account-level routing (key can be plaid account_id or account name)
PLAID_ACCOUNT_BUSINESS_IDS="plaid_account_id_1:biz_34,plaid_account_id_2:biz_95,plaid_account_id_3:biz_321"

# Optional per-business keyword files
KEYWORDS_FILES_BY_BUSINESS="biz_34:keywords/34-grant.json,biz_95:keywords/95-kendall.json,biz_321:keywords/321-walnut.json"
```

If these are not set, behavior stays the same as before: all accounts sync into `WAVE_BUSINESS_ID` and use `KEYWORDS_FILE` (or `keywords.json`).

If you only have one business, you can keep running `uv run plaid_sync.py` directly.

## Deployment Options

| Platform | How |
|----------|-----|
| **GitHub Actions** (recommended) | Fork → setup → done. Runs daily at 9am ET. |
| **Any VPS / cron** | `0 13 * * * cd /path && uv run plaid_sync.py --days 3` (9am ET / 1pm UTC) |

## FAQ

**What if a transaction doesn't match any keyword?**
Goes to your fallback account (set in `keywords.json`). Review in Wave weekly, add keywords as patterns emerge.

**Is it safe to run multiple times?**
Yes. Duplicates are silently skipped.

**What if my bank token expires?**
The script generates a Plaid Hosted Link URL for re-auth. Open it in any browser, log in, done. Token stays the same.

**What about credit card bill payments?**
CC payments (transfers between checking and CC) can't be recorded via Wave's API as inter-account transfers. They go to "Uncategorized Expense" for you to recategorize in Wave as a CC payment. This is the same as Wave's native bank sync. All actual CC charges sync correctly as expenses.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Plaid account (trial = 10 free connections)
- Wave account with API access

## License

MIT
