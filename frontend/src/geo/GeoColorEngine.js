import { GEO_COLORS } from "./GeoColors";

export function paintMap(svgRoot, data) {

    if (!svgRoot) {

        return;

    }

    const paths = svgRoot.querySelectorAll("path");

    paths.forEach(path => {

        const id = path.id;

        const risk = data[id] ?? "UNKNOWN";

        path.style.fill =

            GEO_COLORS[risk] ??

            GEO_COLORS.UNKNOWN;

        path.style.transition =
            "fill 0.25s ease";

    });

}