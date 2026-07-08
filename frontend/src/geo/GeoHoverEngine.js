import { createTooltip } from "./GeoTooltip";

const tooltip = createTooltip();

export function enableHover(svgRoot) {

    if (!svgRoot) {

        return;

    }

    const paths = svgRoot.querySelectorAll("path");

    paths.forEach(path => {

        path.style.cursor = "pointer";

        path.addEventListener("mouseenter", () => {

            path.style.stroke = "#0f172a";
            path.style.strokeWidth = "2";

            tooltip.innerHTML = `

                <div style="font-weight:700;font-size:15px">

                    ${path.getAttribute("name")}

                </div>

                <div style="margin-top:8px;color:#64748b">

                    Click for details

                </div>

            `;

            tooltip.style.display = "block";

        });

        path.addEventListener("mousemove", (e) => {

            tooltip.style.left =
                (e.clientX + 15) + "px";

            tooltip.style.top =
                (e.clientY + 15) + "px";

        });

        path.addEventListener("mouseleave", () => {

            path.style.stroke = "#ffffff";
            path.style.strokeWidth = "1";

            tooltip.style.display = "none";

        });

    });

}