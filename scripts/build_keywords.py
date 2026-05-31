# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Build keywords.json from a Wave General Ledger CSV export."""
import csv, json, re, sys

INPUT_PATH = sys.argv[1]
OUTPUT_PATH = sys.argv[2] if len(sys.argv) > 2 else 'keywords.json'

NON_PNL_ACCOUNTS = {
    'accounts payable', 'accounts receivable', 'cash on hand', 'transfer clearing',
    'owner investment / drawings', "owner's equity", 'mortgages',
}
DEFAULT_SKIP_PATTERNS = ('chase credit', 'automatic payment', 'autopay')
DEFAULT_FALLBACK_EXPENSE = 'Uncategorized Expense'
DEFAULT_FALLBACK_INCOME = 'Uncategorized Income'


def should_learn_from_account(account_name):
    lower = account_name.lower()
    if lower in NON_PNL_ACCOUNTS:
        return False
    return not any(token in lower for token in (
        'checking', 'savings', 'credit card', 'mortgage', 'payable', 'receivable',
        'equity', 'clearing', 'cash on hand', 'disconnected on', 'loan'
    ))


def should_skip_description(desc):
    lower = desc.lower()
    return 'transfer' in lower or lower.startswith('interest paid')

current_account = None
account_transactions = {}
seen_accounts = set()

with open(INPUT_PATH, encoding='utf-8-sig') as f:
    for row in csv.reader(f):
        if len(row) >= 2 and not row[0] and row[1] and not any(row[2:5]):
            current_account = row[1].strip()
            seen_accounts.add(current_account)
        elif len(row) > 2 and current_account and row[2].strip():
            desc = row[2].strip()
            if desc in ('Starting Balance', 'Totals and Ending Balance', 'Balance Change'):
                continue
            if should_learn_from_account(current_account) and not should_skip_description(desc):
                account_transactions.setdefault(current_account, []).append(desc)

def extract_keyword(desc):
    desc = re.sub(r'\*[A-Za-z0-9]{6,}', '', desc)
    desc = re.sub(r'\s+[A-Z0-9]{8,}', '', desc)
    desc = re.sub(r'\s*#\d+.*$', '', desc)
    desc = re.sub(r',\s*\d+$', '', desc)
    desc = re.sub(r'\s+\d{3,}.*$', '', desc)
    desc = re.sub(r'\*\d[\d-]+', '', desc)
    desc = re.sub(r'\s*PO\s+\d+', '', desc)
    desc = re.sub(r'\s*O\*[\d-]+', '', desc)
    desc = re.sub(r'\s*-\s*(NYC|TIMES|UNION).*$', '', desc)
    desc = re.sub(r'\s*-\s*[A-Z].*$', '', desc)
    desc = re.sub(r'\.COM$', '', desc, flags=re.IGNORECASE)
    desc = re.sub(r'\s+(INC|LLC|LTD|SERVICES|ONLINE|RECURRING|PAY|FILM|FESTIVAL)\.?$', '', desc, flags=re.IGNORECASE)
    desc = desc.strip(' .,*').lower()
    if not desc: return ''
    if 'uber eats' in desc: return 'uber eats'
    if desc.startswith('tst'): return 'tst'
    if 'amazon' in desc: return 'amazon'
    if 'ebay' in desc: return 'ebay'
    if 'spitfire' in desc: return 'spitfire'
    if 'citibik' in desc: return 'citibik'
    parts = desc.split()
    if len(parts) >= 2 and len(parts[0]) <= 3:
        return ' '.join(parts[:2])
    return parts[0]

keyword_counts = {}
for account, descs in account_transactions.items():
    for desc in descs:
        kw = extract_keyword(desc)
        if not kw or len(kw) < 3:
            continue
        if kw in ('ach', 'wire', 'payment', 'deposit', 'transfer', 'check', 'payroll',
                  'total', 'incoming', 'mobile', 'interest', 'wave', 'before-tax',
                  '(deleted)', 'super'):
            continue
        keyword_counts.setdefault(kw, {}).setdefault(account, 0)
        keyword_counts[kw][account] += 1

keywords = {}
for kw, accounts in keyword_counts.items():
    best_account = max(accounts, key=accounts.get)
    keywords[kw] = best_account

if 'uber eats' in keywords and 'uber' in keywords:
    keywords['uber'] = 'Travel Expense'

for pattern in DEFAULT_SKIP_PATTERNS:
    keywords[pattern] = None

fallback_income = DEFAULT_FALLBACK_INCOME if DEFAULT_FALLBACK_INCOME in seen_accounts else 'Other'

output = {
    'keywords': dict(sorted(keywords.items())),
    'fallback_expense': DEFAULT_FALLBACK_EXPENSE,
    'fallback_income': fallback_income
}

with open(OUTPUT_PATH, 'w') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f'Generated {len(keywords)} keywords across {len(set(v for v in keywords.values() if v))} categories -> {OUTPUT_PATH}')
