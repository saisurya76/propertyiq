export async function loadGeoJson(path) {

    const response = await fetch(path);

    if (!response.ok) {

        throw new Error(
            `Unable to load ${path}`
        );

    }

    return await response.json();

}