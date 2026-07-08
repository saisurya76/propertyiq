import { useEffect, useState } from "react";

import { loadSvg } from "./SvgLoader";

export default function GeoMap() {

    const [svg, setSvg] = useState("");

    useEffect(() => {

        async function loadMap() {

            try {

                const svgText = await loadSvg(
                    "/maps/countries/india.svg"
                );

                setSvg(svgText);

            }
            catch (err) {

                console.error(err);

            }

        }

        loadMap();

    }, []);

    return (

        <div
            style={{
                width: "100%",
                minHeight: "650px",
                border: "1px solid #dbe4ef",
                borderRadius: "12px",
                background: "#ffffff",
                overflow: "hidden"
            }}
            dangerouslySetInnerHTML={{
                __html: svg
            }}
        />

    );

}