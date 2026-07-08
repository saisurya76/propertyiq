export default function FraudEvidence({ data }) {

  const evidence = data?.evidence ?? [];

  return (

    <div
      style={{
        marginTop: "25px",
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
        EVIDENCE INTELLIGENCE
      </div>

      <div
        style={{
          padding: "20px"
        }}
      >

        {evidence.length === 0 && (

          <div
            style={{
              color: "#64748b"
            }}
          >
            No supporting evidence available.
          </div>

        )}

        {evidence.map((item) => (

          <div
            key={item.evidenceId}
            style={{
              marginBottom: "18px",
              border: "1px solid #e5e7eb",
              borderRadius: "10px",
              padding: "18px",
              background: "#fafafa"
            }}
          >

            <h3
              style={{
                marginTop: 0
              }}
            >
              {item.sourceName}
            </h3>

            <table
              style={{
                width: "100%",
                borderCollapse: "collapse"
              }}
            >

              <tbody>

                <tr>

                  <td><strong>Source</strong></td>

                  <td>{item.sourceType}</td>

                </tr>

                <tr>

                  <td><strong>Confidence</strong></td>

                  <td>{Math.round(item.confidence * 100)}%</td>

                </tr>

                <tr>

                  <td><strong>Published</strong></td>

                  <td>{item.publishedDate}</td>

                </tr>

                <tr>

                  <td><strong>Summary</strong></td>

                  <td>{item.summary}</td>

                </tr>

                <tr>

                  <td><strong>Citation</strong></td>

                  <td>{item.citation}</td>

                </tr>

                <tr>

                  <td><strong>Source URL</strong></td>

                  <td>{item.url}</td>

                </tr>

              </tbody>

            </table>

          </div>

        ))}

      </div>

    </div>

  );

}