const fraudIcons = {

    TITLE_CHAIN_RISK: "📜",

    REVENUE_RECORD_MANIPULATION: "📑",

    GOVERNMENT_LAND_DISPUTES: "🏛️",

    MULTIPLE_SALE_FRAUD: "🏘️",

    FORGED_DOCUMENTS: "📄",

    MORTGAGE_FRAUD: "🏦",

    ILLEGAL_LAYOUTS: "🗺️",

    BUILDER_FRAUD: "🏗️",

    APPROVAL_MISREPRESENTATION: "✔️",

    SURVEY_MANIPULATION: "📐"

};

const countryFlags = {

    India: "🇮🇳",

    Thailand: "🇹🇭",

    Singapore: "🇸🇬",

    USA: "🇺🇸",

    UK: "🇬🇧",

    Australia: "🇦🇺",

    Malaysia: "🇲🇾",

    Indonesia: "🇮🇩",

    UAE: "🇦🇪"

};

export default function GlobalFraudMatrix({ data }) {

    const matrix = data?.globalMatrix;

    const countries = matrix?.countries ?? [];

    const fraudTypes = matrix?.fraudTypes ?? [];

    const cells = matrix?.cells ?? [];

    return (

        <>

                <div
                    style={{
                        display: "flex",
                        justifyContent: "center",
                        marginBottom: "24px"
                    }}
                >

                <div
                    style={{
                        border: "1px solid #d8dee8",
                        borderRadius: "10px",
                        padding: "12px 22px",
                        display: "flex",
                        alignItems: "center",
                        gap: "26px",
                        background: "#ffffff",
                        boxShadow: "0 1px 4px rgba(0,0,0,.05)"
                    }}
                >

                    <div
                        style={{
                            fontWeight: 700,
                            color: "#334155",
                            marginRight: "10px"
                        }}
                    >
                        RISK LEVEL
                    </div>

                    <div style={{display:"flex",alignItems:"center",gap:"8px"}}>
                        <span style={{
                            width:16,
                            height:16,
                            borderRadius:"50%",
                            background:"#d7191c",
                            display:"inline-block"
                        }}/>
                        Very High
                    </div>

                    <div style={{display:"flex",alignItems:"center",gap:"8px"}}>
                        <span style={{
                            width:16,
                            height:16,
                            borderRadius:"50%",
                            background:"#f57c00",
                            display:"inline-block"
                        }}/>
                        High
                    </div>

                    <div style={{display:"flex",alignItems:"center",gap:"8px"}}>
                        <span style={{
                            width:16,
                            height:16,
                            borderRadius:"50%",
                            background:"#fbc02d",
                            display:"inline-block"
                        }}/>
                        Medium
                    </div>

                    <div style={{display:"flex",alignItems:"center",gap:"8px"}}>
                        <span style={{
                            width:16,
                            height:16,
                            borderRadius:"50%",
                            background:"#43a047",
                            display:"inline-block"
                        }}/>
                        Low
                    </div>

                    <div style={{display:"flex",alignItems:"center",gap:"8px"}}>
                        <span style={{
                            width:16,
                            height:16,
                            borderRadius:"50%",
                            background:"#b8e186",
                            display:"inline-block"
                        }}/>
                        Very Low
                    </div>

                </div>

            </div>

            <div
                style={{
                    background: "#081c33",
                    color: "#ffffff",
                    padding: "18px 28px",
                    borderRadius: "12px 12px 0 0"
                }}
            >

                <div
                    style={{
                        display: "grid",
                        gridTemplateColumns: "1.6fr 1fr",
                        columnGap: "40px",
                        alignItems: "center"
                    }}
                >

                    <div>

                        <div
                            style={{
                                fontSize: "24px",
                                fontWeight: 800,
                                lineHeight: 1.1,
                                whiteSpace: "nowrap"
                            }}
                        >
                            GLOBAL FRAUD TAXONOMY HEAT MAP
                        </div>

                        <div
                            style={{
                                marginTop: "6px",
                                fontSize: "14px",
                                opacity: .9
                            }}
                        >
                            Real Estate Fraud Risk by Country & Fraud Category
                        </div>

                    </div>

                    <div
                        style={{
                            textAlign: "right",
                            fontSize: "14px",
                            lineHeight: 1.4
                        }}
                    >

                        <div>
                            Based on public reports,
                            regulatory actions,
                            court cases &
                            credible media
                        </div>

                        <div
                            style={{
                                marginTop: "10px",
                                fontWeight: 700
                            }}
                        >
                            Last Updated: May 2025
                        </div>

                    </div>

                </div>

            </div>

            <div
                style={{
                    background: "#ffffff",
                    border: "1px solid #dbe4ef",
                    borderTop: "none",
                    borderRadius: "0 0 12px 12px",
                    overflow: "hidden",
                    boxShadow: "0 2px 10px rgba(0,0,0,.08)"
                }}
            >

                <table
                        style={{
                            width: "100%",
                            borderCollapse: "collapse",
                            tableLayout: "fixed",
                            fontFamily: "Inter, sans-serif",
                            fontSize: "14px"
                        }}
                    >

                    <thead
                        style={{
                            background: "#0b2545",
                            color: "#ffffff"
                        }}
                    >

                        <tr>

                            <th
                                style={{
                                    textAlign: "left",
                                    padding: "14px 18px",
                                    width: "40%",
                                    borderRight: "1px solid #1f3a5a"
                                }}
                            >
                                Fraud Type
                            </th>

                            {countries.map((country) => (

                                <th
                                    key={country}
                                    style={{
                                        width: `${60 / countries.length}%`,
                                        padding: "12px 18px",
                                        textAlign: "center",
                                        borderLeft: "1px solid #1f3a5a"
                                    }}
                                >
                                    <div
                                        style={{
                                            display: "flex",
                                            flexDirection: "column",
                                            alignItems: "center",
                                            gap: "4px"
                                        }}
                                    >

                                        <div
                                            style={{
                                                fontSize: "20px"
                                            }}
                                        >
                                            {countryFlags[country]}
                                        </div>

                                        <div
                                            style={{
                                                fontWeight: 700,
                                                fontSize: "12px",
                                                letterSpacing: ".5px"
                                            }}
                                        >
                                            {country.toUpperCase()}
                                        </div>

                                    </div>
                                </th>

                            ))}

                        </tr>

                    </thead>

                    <tbody>

                        {fraudTypes.map((fraud, index) => (

                            <tr
                                key={fraud.id}
                                style={{
                                    borderTop: "1px solid #e5e7eb"
                                }}
                            >

                                <td
                                    style={{
                                        padding: "14px 18px",
                                        textAlign: "left",
                                        verticalAlign: "top"
                                    }}
                                >
                                    <div
                                        style={{
                                            display: "flex",
                                            gap: "12px",
                                            alignItems: "flex-start"
                                        }}
                                    >

                                        <div
                                            style={{
                                                width: "34px",
                                                fontWeight: 700,
                                                color: "#64748b",
                                                flexShrink: 0
                                            }}
                                        >
                                            {String(index + 1).padStart(2, "0")}
                                        </div>

                                        <div>

                                            <div
                                                style={{
                                                    display: "flex",
                                                    alignItems: "center",
                                                    gap: "10px",
                                                    marginBottom: "4px"
                                                }}
                                            >

                                                <span
                                                    style={{
                                                        fontSize: "22px",
                                                        width: "28px",
                                                        textAlign: "center"
                                                    }}
                                                >
                                                    {fraudIcons[fraud.id]}
                                                </span>

                                                <span
                                                    style={{
                                                        fontWeight: 700,
                                                        fontSize: "15px"
                                                    }}
                                                >
                                                    {fraud.displayName}
                                                </span>

                                            </div>

                                            <div
                                                style={{
                                                    color: "#64748b",
                                                    lineHeight: "18px",
                                                    paddingLeft: "38px"
                                                }}
                                            >
                                                {fraud.description}
                                            </div>

                                        </div>

                                    </div>

                                </td>

                                {countries.map((country) => {

                                    const cell = cells.find(
                                        c =>
                                            c.country === country &&
                                            c.fraudTypeId === fraud.id
                                    );

                                    const riskColors = {

                                        RED: {
                                            bg: "#fde8e8",
                                            dot: "#d7191c"
                                        },

                                        ORANGE: {
                                            bg: "#fff2df",
                                            dot: "#f57c00"
                                        },

                                        YELLOW: {
                                            bg: "#fff9dc",
                                            dot: "#fbc02d"
                                        },

                                        GREEN: {
                                            bg: "#eef9ea",
                                            dot: "#43a047"
                                        },

                                        LIGHT_GREEN: {
                                            bg: "#f6fcf3",
                                            dot: "#8bc34a"
                                        }

                                    };

                                    const risk = riskColors[cell?.color] ?? {

                                        bg: "#f5f5f5",

                                        dot: "#d0d0d0"

                                    };

                                    return (

                                        <td
                                            key={country}
                                            style={{
                                                padding: "12px",
                                                textAlign: "center"
                                            }}
                                        >

                                            <div
                                                style={{
                                                    width: "110px",
                                                    height: "34px",
                                                    margin: "auto",
                                                    borderRadius: "8px",
                                                    display: "flex",
                                                    justifyContent: "center",
                                                    alignItems: "center",
                                                    background: risk.bg
                                                }}
                                            >

                                                <div
                                                    style={{
                                                        width: "14px",
                                                        height: "14px",
                                                        borderRadius: "50%",
                                                        background: risk.dot
                                                    }}
                                                />

                                            </div>

                                        </td>

                                    );

                                })}

                            </tr>

                        ))}

                    </tbody>

                </table>

            </div>

        </>

    );

}