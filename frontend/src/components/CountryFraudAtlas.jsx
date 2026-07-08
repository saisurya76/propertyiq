export default function CountryFraudAtlas({ data }) {

  return (

    <div
      style={{
        marginTop: "15px",
        background: "#ffffff",
        border: "1px solid #dbe4ef",
        borderRadius: "14px",
        overflow: "hidden"
      }}
    >

      <div
        style={{
          background: "#0f172a",
          color: "#ffffff",
          padding: "14px 18px",
          fontWeight: "700"
        }}
      >
        COUNTRY FRAUD ATLAS
      </div>

      <div
        style={{
          padding: "20px"
        }}
      >

        <div
          style={{
            display: "flex",
            gap: "20px",
            flexWrap: "wrap",
            marginBottom: "20px",
            fontSize: "14px"
          }}
        >

          <span>🔴 Very High</span>

          <span>🟠 High</span>

          <span>🟡 Medium</span>

          <span>🟢 Low</span>

          <span>⚪ Very Low</span>

        </div>

        <div
          style={{
            height: "420px",
            border: "2px dashed #cbd5e1",
            borderRadius: "10px",
            background: "#f8fafc",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            color: "#64748b",
            fontSize: "18px",
            fontWeight: "600"
          }}
        >
          Dynamic Country Fraud Atlas
        </div>

        <div
          style={{
            marginTop: "20px",
            fontSize: "13px",
            color: "#64748b"
          }}
        >
          Last Updated : {data?.lastUpdated ?? "Awaiting live intelligence"}
        </div>

      </div>

    </div>

  );

}