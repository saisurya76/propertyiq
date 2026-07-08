import CityFraudAtlas from "./CityFraudAtlas";
import CountryFraudAtlas from "./CountryFraudAtlas";
import GlobalFraudTaxonomy from "./GlobalFraudTaxonomy";
import FraudEvidence from "./FraudEvidence";
import FraudCitations from "./FraudCitations";

function StatusCircle({ color }) {

  const colors = {
    RED: "#dc2626",
    ORANGE: "#ea580c",
    YELLOW: "#facc15",
    GREEN: "#16a34a",
    BLUE: "#2563eb",
    GREY: "#9ca3af"
  };

  const base = colors[color] || colors.GREY;

  return (

    <div
      style={{
        width: "22px",
        height: "22px",
        margin: "0 auto",
        borderRadius: "50%",

        background: `radial-gradient(circle at 30% 30%,
            rgba(255,255,255,.95),
            ${base} 45%,
            ${base} 70%,
            rgba(0,0,0,.30) 100%)`,

        boxShadow:
          "inset 0 2px 3px rgba(255,255,255,.6), " +
          "inset 0 -3px 5px rgba(0,0,0,.30), " +
          "0 1px 3px rgba(0,0,0,.35)"
      }}
    />

  );

}

function FraudTable({ title, items }) {

  return (

    <div
      style={{
        marginTop: "25px",
        background: "#ffffff",
        border: "1px solid #e5e7eb",
        borderRadius: "14px",
        overflow: "hidden"
      }}
    >

      <div
        style={{
          background: "#0f172a",
          color: "#ffffff",
          padding: "14px 18px",
          fontWeight: "700",
          letterSpacing: "1px"
        }}
      >
        {title}
      </div>

      <table
        style={{
          width: "100%",
          borderCollapse: "collapse"
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
                padding: "12px"
              }}
            >
              Fraud Type
            </th>

            <th
            style={{
                width: "120px"
            }}
            >
            Status
            </th>

          </tr>

        </thead>

        <tbody>

          {items?.map((item) => (

            <tr
              key={item.id}
              style={{
                borderTop: "1px solid #e5e7eb"
              }}
            >

              <td
                style={{
                  padding: "12px"
                }}
              >
                <strong>
                  {item.displayName}
                </strong>

                <div
                  style={{
                    color: "#64748b",
                    fontSize: "13px",
                    marginTop: "4px"
                  }}
                >
                  {item.description}
                </div>

              </td>

              <td
                style={{
                    textAlign: "center"
                }}
                >
                <StatusCircle color={item.color} />
                </td>

            </tr>

          ))}

        </tbody>

      </table>

    </div>

  );

}

export default function FraudIntelligence({ result }) {

  if (!result?.fraudIntelligence) {

    return null;

  }

  const fraud = result.fraudIntelligence;

  return (

    <div
      style={{
        maxWidth: "1100px",
        margin: "35px auto"
      }}
    >

      <div
        style={{
          fontSize: "13px",
          letterSpacing: "2px",
          fontWeight: "700",
          color: "#64748b",
          marginBottom: "12px"
        }}
      >
        FRAUD INTELLIGENCE
      </div>

      <FraudTable
        title="CITY FRAUD INTELLIGENCE"
        items={fraud.city}
      />

      <CityFraudAtlas
            data={fraud}
        />

      <FraudTable
        title="COUNTRY FRAUD INTELLIGENCE"
        items={fraud.country}
      />

      <CountryFraudAtlas
            data={fraud}
        />

      <FraudTable
        title="GLOBAL FRAUD TAXONOMY"
        items={fraud.globalTaxonomy}
      />

      <GlobalFraudTaxonomy
            data={fraud}
        />

        <FraudEvidence
            data={fraud}
        />

        <FraudCitations
            data={fraud}
        />
        
    </div>

  );

}