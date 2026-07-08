export default function GlobalFraudMatrix({ data }) {

  const countries = data?.countries ?? [];
  const fraudTypes = data?.fraudTypes ?? [];

  return (

    <div
      style={{
        overflowX: "auto",
        border: "1px solid #e5e7eb",
        borderRadius: "10px"
      }}
    >

      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          minWidth: "900px"
        }}
      >

        <thead>

          <tr
            style={{
              background: "#f8fafc"
            }}
          >

            <th
              style={{
                textAlign: "left",
                padding: "14px",
                minWidth: "260px"
              }}
            >
              Fraud Type
            </th>

            {countries.map((country) => (

              <th
                key={country.code}
                style={{
                  padding: "12px",
                  textAlign: "center",
                  whiteSpace: "nowrap"
                }}
              >
                {country.name}
              </th>

            ))}

          </tr>

        </thead>

        <tbody>

          {fraudTypes.map((fraud) => (

            <tr
              key={fraud.id}
              style={{
                borderTop: "1px solid #e5e7eb"
              }}
            >

              <td
                style={{
                  padding: "14px"
                }}
              >
                <strong>
                  {fraud.displayName}
                </strong>

                <div
                  style={{
                    fontSize: "13px",
                    color: "#64748b",
                    marginTop: "4px"
                  }}
                >
                  {fraud.description}
                </div>

              </td>

              {countries.map((country) => (

                <td
                  key={country.code}
                  style={{
                    textAlign: "center",
                    padding: "12px"
                  }}
                >
                  —
                </td>

              ))}

            </tr>

          ))}

        </tbody>

      </table>

    </div>

  );

}