import { useEffect, useRef, useState } from "react";

import { loadSvg } from "./SvgLoader";
import { paintMap } from "./GeoColorEngine";
import { enableHover } from "./GeoHoverEngine";

export default function GeoMap() {

    const [svg, setSvg] = useState("");

    const containerRef = useRef(null);

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

    useEffect(() => {

        if (!svg) {

            return;

        }

        const timer = setTimeout(() => {

            const svgRoot =
                containerRef.current.querySelector("svg");

            paintMap(svgRoot, {

                INAN: "VERY_HIGH",

                INTG: "HIGH",

                INKA: "LOW",

                INMH: "MEDIUM",

                INTN: "VERY_LOW"

            });

            enableHover(svgRoot);
            
        }, 50);

        return () => clearTimeout(timer);

    }, [svg]);

    return (

        <div

            ref={containerRef}

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