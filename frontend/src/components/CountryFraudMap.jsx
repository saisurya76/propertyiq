function getColor(color) {

  switch (color) {

    case "RED":
      return "#dc2626";

    case "ORANGE":
      return "#ea580c";

    case "YELLOW":
      return "#facc15";

    case "GREEN":
      return "#16a34a";

    default:
      return "#9ca3af";

  }

}

export default function CountryFraudMap({ data }) {

  const items = data?.country ?? [];

  return (

    <div
      style={{
        minHeight: "420px",
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(220px,1fr))",
        gap: "16px"
      }}
    >

      {items.map((item) => (

        <div
          key={item.id}
          style={{
            background: getColor(item.color),
            color: "#ffffff",
            borderRadius: "12px",
            padding: "18px",
            minHeight: "110px",
            boxShadow: "0 3px 8px rgba(0,0,0,.15)"
          }}
        >

          <div
            style={{
              fontWeight: "700",
              fontSize: "15px"
            }}
          >
            {item.displayName}
          </div>

        </div>

      ))}

    </div>

  );

}