import indiaFraudAtlas from "../assets/fraud/india_fraud_atlas.png";
import globalFraudTaxonomy from "../assets/fraud/global_fraud_taxonomy.png";

function FraudIntelligenceStatic() {

    return (

        <div
            style={{
                maxWidth: "1100px",
                margin: "40px auto"
            }}
        >

            <div
                style={{
                    fontSize: "30px",
                    fontWeight: "700",
                    color: "#0f172a",
                    marginBottom: "12px"
                }}
            >
                Fraud Intelligence
            </div>

            <div
                style={{
                    color: "#64748b",
                    lineHeight: "1.8",
                    marginBottom: "30px"
                }}
            >
                PropertyIQ Fraud Intelligence provides independent buyer awareness
                using curated fraud intelligence compiled from public records,
                regulatory actions, court cases and credible market investigations.
                The following visual atlases summarize common real estate fraud
                patterns to support buyer due diligence.
            </div>

            <img
                src={indiaFraudAtlas}
                alt="India Fraud Atlas"
                style={{
                    width: "100%",
                    marginBottom: "40px",
                    borderRadius: "10px",
                    boxShadow: "0 3px 12px rgba(0,0,0,.12)"
                }}
            />

            <img
                src={globalFraudTaxonomy}
                alt="Global Fraud Taxonomy"
                style={{
                    width: "100%",
                    borderRadius: "10px",
                    boxShadow: "0 3px 12px rgba(0,0,0,.12)"
                }}
            />

        </div>

    );

}

export default FraudIntelligenceStatic;