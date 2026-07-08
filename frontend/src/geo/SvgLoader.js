export async function loadSvg(path) {

    const response = await fetch(path);

    if (!response.ok) {

        throw new Error(
            `Unable to load SVG: ${path}`
        );

    }

    return await response.text();

}