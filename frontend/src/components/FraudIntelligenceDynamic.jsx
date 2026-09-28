import indiaFraudAtlas from "../assets/fraud/india_fraud_atlas.png";
import globalFraudTaxonomy from "../assets/fraud/global_fraud_taxonomy.png";
import fraudEvidenceSources from "../assets/fraud/fraud_evidence_sources.png";
import { GEO_COLORS } from "../geo/GeoColors";

const reportLinkStyle = {
    color: "#ea580c",
    fontWeight: "600",
    textDecoration: "none",
    fontSize: "15px",
    transition: "all 0.2s ease"
};

const sectionIntroStyle = {
    color: "#64748b",
    lineHeight: "1.8",
    marginBottom: "30px"
};

const imgStyle = {
    width: "100%",
    marginBottom: "16px",
    borderRadius: "10px",
    boxShadow: "0 3px 12px rgba(0,0,0,.12)"
};

const linkWrapStyle = {
    marginTop: "14px",
    marginBottom: "40px",
    textAlign: "center"
};

function riskBadgeStyle(riskLevel) {
    const bg = GEO_COLORS[riskLevel] || GEO_COLORS.UNKNOWN;
    // VERY_LOW/UNKNOWN use a light fill, so dark text reads better than white
    const lightBg = riskLevel === "VERY_LOW" || riskLevel === "UNKNOWN";
    return {
        display: "inline-block",
        padding: "2px 10px",
        borderRadius: "999px",
        fontSize: "12px",
        fontWeight: "700",
        color: lightBg ? "#334155" : "#fff",
        background: bg
    };
}

function RiskTypeList({ title, assessments, emptyNote }) {
    const applicable = (assessments || []).filter((a) => a.applicable);

    return (
        <div style={{ marginBottom: "28px" }}>
            <div style={{ fontWeight: "700", marginBottom: "10px", color: "#1e293b" }}>
                {title} — {applicable.length} of {assessments?.length || 0} fraud types flagged
            </div>

            {applicable.length === 0 ? (
                <p style={{ color: "#64748b", fontSize: "14px" }}>{emptyNote}</p>
            ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {applicable.map((a) => (
                        <div
                            key={a.id}
                            style={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                                padding: "10px 14px",
                                border: "1px solid #e2e8f0",
                                borderRadius: "8px"
                            }}
                        >
                            <div>
                                <div style={{ fontWeight: "600", color: "#1e293b" }}>{a.displayName}</div>
                                <div style={{ fontSize: "13px", color: "#64748b" }}>{a.description}</div>
                            </div>
                            <span style={riskBadgeStyle(a.riskLevel)}>
                                {a.riskLevel.replace("_", " ")} · {a.evidenceCount} evidence
                            </span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

/* Real per-property fraud data (city/country risk breakdown + evidence,
   already computed and geo-filtered by the backend) plus the general
   fraud-taxonomy/methodology visuals — swapped in for the old
   FraudIntelligenceStatic, which showed the same India-only atlas image
   and "Open ... Report for India" link to every country's users
   regardless of which property they were assessing. */
function FraudIntelligenceDynamic({ fraudIntelligence, country }) {

    const isIndia = (country || "").trim().toLowerCase() === "india";

    return (
        <div style={{ maxWidth: "1100px", margin: "0 auto" }}>

            <div style={sectionIntroStyle}>
                PropertyIQ Fraud Intelligence provides independent buyer awareness using
                curated fraud intelligence compiled from public records, regulatory actions,
                court cases and credible market investigations, cross-checked against this
                specific property's own location.
            </div>

            {fraudIntelligence && (
                <>
                    <RiskTypeList
                        title={`City-Level Risk — ${fraudIntelligence.status?.status === "AVAILABLE" ? "evidence on file" : "limited evidence"}`}
                        assessments={fraudIntelligence.city}
                        emptyNote="No fraud evidence currently on file for this specific city. This reflects PropertyIQ's evidence library coverage, not a guarantee the area is risk-free."
                    />

                    <RiskTypeList
                        title="Country-Level Risk"
                        assessments={fraudIntelligence.country}
                        emptyNote="No fraud evidence currently on file for this country yet — PropertyIQ's evidence library is actively expanding beyond its initial India coverage."
                    />

                    {fraudIntelligence.evidence?.length > 0 && (
                        <div style={{ marginBottom: "30px" }}>
                            <div style={{ fontWeight: "700", marginBottom: "10px", color: "#1e293b" }}>
                                Evidence & Citations
                            </div>
                            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                                {fraudIntelligence.evidence.map((e) => (
                                    <div key={e.evidenceId} style={{ fontSize: "13px", color: "#475569", borderLeft: "3px solid #ea580c", paddingLeft: "10px" }}>
                                        <strong>{e.sourceName}</strong> ({e.sourceType}) — {e.summary}{" "}
                                        {e.url && (
                                            <a href={e.url} target="_blank" rel="noopener noreferrer" style={{ color: "#ea580c" }}>
                                                source ↗
                                            </a>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    <div style={{ fontSize: "12px", color: "#94a3b8", marginBottom: "40px" }}>
                        Report ID: {fraudIntelligence.status?.reportId}
                    </div>
                </>
            )}

            {isIndia ? (
                <>
                    <img src={indiaFraudAtlas} alt="India Fraud Atlas" style={imgStyle} />
                    <div style={linkWrapStyle}>
                        <a
                            href="/fraud/india_real_estate_fraud_atlas.html"
                            target="_blank"
                            rel="noopener noreferrer"
                            style={reportLinkStyle}
                        >
                            Open Full Fraud Intelligence Report for India ↗
                        </a>
                    </div>
                </>
            ) : (
                <p style={{ color: "#64748b", fontSize: "14px", marginBottom: "30px" }}>
                    A dedicated visual fraud atlas for {country || "this country"} hasn't been published yet — the
                    fraud-type taxonomy and per-property evidence above still apply here in full.
                </p>
            )}

            <img src={globalFraudTaxonomy} alt="Global Fraud Taxonomy" style={imgStyle} />
            <div style={linkWrapStyle}>
                <a
                    href="/fraud/real_estate_fraud_snapshot.html"
                    target="_blank"
                    rel="noopener noreferrer"
                    style={reportLinkStyle}
                >
                    Open Full Fraud Intelligence Report - Global ↗
                </a>
            </div>

            <img src={fraudEvidenceSources} alt="Fraud Evidence Sources" style={imgStyle} />

        </div>
    );
}

export default FraudIntelligenceDynamic;
