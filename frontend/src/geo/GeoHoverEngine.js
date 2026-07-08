export function enableHover(svgRoot) {

    if (!svgRoot) {

        return;

    }

    const paths = svgRoot.querySelectorAll("path");

    paths.forEach(path => {

        path.style.cursor = "pointer";

        path.addEventListener("mouseenter", () => {

            path.dataset.previousFill = path.style.fill;

            path.style.stroke = "#0f172a";
            path.style.strokeWidth = "2";

            console.log(
                path.getAttribute("name")
            );

        });

        path.addEventListener("mouseleave", () => {

            path.style.stroke = "#ffffff";
            path.style.strokeWidth = "1";

        });

    });

}