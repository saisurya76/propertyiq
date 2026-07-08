export function createTooltip() {

    const tooltip = document.createElement("div");

    tooltip.style.position = "fixed";
    tooltip.style.pointerEvents = "none";
    tooltip.style.background = "#ffffff";
    tooltip.style.border = "1px solid #dbe4ef";
    tooltip.style.borderRadius = "10px";
    tooltip.style.padding = "12px";
    tooltip.style.boxShadow =
        "0 8px 24px rgba(0,0,0,0.15)";
    tooltip.style.fontSize = "14px";
    tooltip.style.color = "#0f172a";
    tooltip.style.display = "none";
    tooltip.style.zIndex = "9999";

    document.body.appendChild(tooltip);

    return tooltip;

}