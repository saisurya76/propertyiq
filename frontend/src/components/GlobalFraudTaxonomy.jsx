import GlobalFraudMatrix from "./GlobalFraudMatrix";

export default function GlobalFraudTaxonomy({ data }) {

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
        GLOBAL FRAUD RISK MATRIX
      </div>

      <div
        style={{
          padding: "20px"
        }}
      >

      
        <GlobalFraudMatrix
            data={data}
        />

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