from backend.fraud_intelligence.engine import (
    generate_fraud_report
)

report = generate_fraud_report(

    country="IN",

    state="Telangana",

    city="Hyderabad",

    locality="Gachibowli"
)

print()
print("========== STATUS ==========")
print(report.status)

print()
print("========== CITY ==========")

for item in report.city:

    print(
        f"{item.fraud_type.display_name:<40}"
        f"{item.risk_level:<10}"
        f"{item.color:<8}"
        f"Evidence={item.evidence_count}"
    )

print()
print("========== COUNTRY ==========")

for item in report.country:

    print(
        f"{item.fraud_type.display_name:<40}"
        f"{item.risk_level:<10}"
        f"{item.color:<8}"
        f"Evidence={item.evidence_count}"
    )

print()
print("========== GLOBAL ==========")

for item in report.global_taxonomy:

    print(
        f"{item.fraud_type.display_name:<40}"
        f"{item.risk_level:<10}"
        f"{item.color:<8}"
        f"Evidence={item.evidence_count}"
    )

print()
print("========== EVIDENCE ==========")

for item in report.evidence:
    print(item)

print()
print("========== CITATIONS ==========")

for item in report.citations:
    print(item)

print()

print(report.global_matrix.countries)

print()

print(len(report.global_matrix.fraud_types))

print()

print(len(report.global_matrix.cells))    