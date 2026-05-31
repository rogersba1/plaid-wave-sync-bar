# Keywords Guide

Keywords are auto-generated during setup from your Wave general ledger CSV. This file documents the format for manual editing.

## Format

```json
{
  "keywords": {
    "vendor keyword": "Wave Account Name",
    "another vendor": "Wave Account Name",
    "skip keyword": null
  },
  "fallback_expense": "Uncategorized Expense",
  "fallback_income": "Other"
}
```

## Rules

- Keywords are **lowercase** substrings matched against transaction descriptions
- Values must **exactly** match a Wave account name (run `uv run plaid_sync.py --dump-accounts` to see them)
- Only use Expense or Income accounts (NOT Asset, Equity, or Liability)
- Use `null` only for transactions you explicitly want to skip
- Shorter keywords are better (e.g., "adobe" not "adobe creative cloud")

## Validate

```bash
uv run plaid_sync.py --dump-accounts   # shows ✓/✗ for each keyword target
uv run plaid_sync.py --dry-run --days 90  # shows what would be categorized
```

## Regenerate

To rebuild from a new CSV export:

```bash
uv run scripts/build_keywords.py "path/to/your.csv"
```

To maintain separate keyword maps per business:

```bash
uv run scripts/build_keywords.py "imports/34 Grant Fourplex Account Transactions 2026-05-30-00_56.csv" "keywords/34-grant.json"
KEYWORDS_FILE=keywords/34-grant.json uv run plaid_sync.py --dry-run --days 30
```

If `KEYWORDS_FILE` is not set, the sync defaults to `keywords.json`.
