from backend.fraud_intelligence.evidence_loader import load_evidence
from backend.fraud_intelligence.evidence_search import search_evidence

records = load_evidence(
    "backend/data/fraud/evidence.json"
)

matches = search_evidence(
    records,

    country="IN",

    state="Telangana",

    city="Hyderabad",

    locality="Gachibowli"
)

print()

print(f"Found {len(matches)} matching evidence record(s)")

print()

for item in matches:

    print(item)