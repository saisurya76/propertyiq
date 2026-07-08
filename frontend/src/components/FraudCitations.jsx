export default function FraudCitations({ data }) {

  const citations = data?.citations ?? [];

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
        REFERENCES
      </div>

      <div
        style={{
          padding: "20px"
        }}
      >

        {citations.length === 0 && (

          <div
            style={{
              color: "#64748b"
            }}
          >
            No citations available.
          </div>

        )}

        <ol
          style={{
            margin: 0,
            paddingLeft: "22px"
          }}
        >

          {citations.map((citation, index) => (

            <li
              key={index}
              style={{
                marginBottom: "12px",
                lineHeight: "1.6"
              }}
            >
              {citation}
            </li>

          ))}

        </ol>

      </div>

    </div>

  );

}