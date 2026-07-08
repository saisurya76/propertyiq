export default function GlobalFraudMatrix({ data }) {

 const matrix = data?.globalMatrix;
 const countries = matrix?.countries ?? [];
 const fraudTypes = matrix?.fraudTypes ?? [];
 const cells = matrix?.cells ?? [];

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
                    key={country}
                    style={{
                    padding: "12px",
                    textAlign: "center",
                    whiteSpace: "nowrap"
                    }}
                >
                    {country}
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

              {countries.map((country) => {

                const cell =
                    cells.find(

                    c =>

                        c.country === country &&

                        c.fraudTypeId === fraud.id

                    );

                return (

                    <td
                    key={country}
                    style={{
                        textAlign: "center",
                        padding: "12px",
                        fontSize: "22px"
                    }}
                    >

                    {cell?.color === "RED" && "🔴"}

                    {cell?.color === "ORANGE" && "🟠"}

                    {cell?.color === "YELLOW" && "🟡"}

                    {cell?.color === "GREEN" && "🟢"}

                    {!cell && "⚪"}

                    </td>

                );

                })}

            </tr>

          ))}

        </tbody>

      </table>

    </div>

  );

}