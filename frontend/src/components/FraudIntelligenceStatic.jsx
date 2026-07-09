import indiaFraudAtlas from "../assets/fraud/india_fraud_atlas.png";
import globalFraudTaxonomy from "../assets/fraud/global_fraud_taxonomy.png";
import fraudEvidenceSources from "../assets/fraud/fraud_evidence_sources.png";

const reportLinkStyle = {
    color: "#ea580c",
    fontWeight: "600",
    textDecoration: "none",
    fontSize: "15px",
    transition: "all 0.2s ease"
};

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

            <div
                style={{
                    marginTop: "14px",
                    marginBottom: "40px",
                    textAlign: "center"
                }}
            >
                <a
                    href="/fraud/india_real_estate_fraud_atlas.html"
                    target="_blank"
                    rel="noopener noreferrer"
                    style={reportLinkStyle}
                    onMouseEnter={(e) => {
                        e.target.style.color = "#c2410c";
                        e.target.style.textDecoration = "underline";
                    }}

                    onMouseLeave={(e) => {
                        e.target.style.color = "#ea580c";
                        e.target.style.textDecoration = "none";
                    }}
                >
                    Open Full Fraud Intelligence Report for India ↗
                </a>
            </div>

            <img
                src={globalFraudTaxonomy}
                alt="Global Fraud Taxonomy"
                style={{
                    width: "100%",
                    marginBottom: "40px",
                    borderRadius: "10px",
                    boxShadow: "0 3px 12px rgba(0,0,0,.12)"
                }}
            />

            <div
                style={{
                    marginTop: "14px",
                    marginBottom: "40px",
                    textAlign: "center"
                }}
            >
                <a
                    href="/fraud/real_estate_fraud_snapshot.html"
                    target="_blank"
                    rel="noopener noreferrer"
                    style={reportLinkStyle}
                    onMouseEnter={(e) => {
                        e.target.style.color = "#c2410c";
                        e.target.style.textDecoration = "underline";
                    }}

                    onMouseLeave={(e) => {
                        e.target.style.color = "#ea580c";
                        e.target.style.textDecoration = "none";
                    }}
                >
                    Open Full Fraud Intelligence Report - Global ↗
                </a>
            </div>

             <img
                src={fraudEvidenceSources}
                alt="Fraud Evidence Sources"
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