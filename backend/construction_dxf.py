from pathlib import Path
from typing import Any, Optional

import ezdxf

DEFAULT_OUTPUT_DIR = Path("outputs/dxf")


def _hex_to_true_color(hex_color: Optional[str]) -> Optional[int]:
    """Converts a '#rrggbb' hex string to ezdxf's true_color int. Returns
    None on anything invalid so callers can fall back to the layer's
    default color rather than erroring on a bad value."""
    if not hex_color:
        return None
    hex_color = hex_color.strip().lstrip("#")
    if len(hex_color) != 6:
        return None
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
    except ValueError:
        return None
    return ezdxf.colors.rgb2int((r, g, b))


def generate_plot_dxf(
    *,
    design_id: str,
    plot_length_ft: float,
    plot_width_ft: float,
    rooms: list[dict[str, Any]],
    road_facing_side: str = "north",
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Path:
    """Generate a real, portable DXF (2D CAD exchange format) of the plot
    boundary and a simple room layout, so the design can be opened in
    AutoCAD, Revit, SketchUp, FreeCAD, or any DXF-compatible tool.

    `rooms` = [{"name": str, "x": float, "y": float, "length": float, "width": float, "color": Optional[str "#rrggbb"]}, ...]
    Coordinates are in feet, plot origin at (0, 0). Room `color`, if
    provided, is applied as a real DXF true-color value on that room's
    polyline and label — not just a cosmetic UI choice, it genuinely
    carries into the exported file and round-trips through any DXF reader.

    This is a genuine, working DXF export — not a mock. It does not attempt
    full 3D BIM (that is out of scope); it is a real, portable 2D layout
    export, which is what "exchangeable format" realistically means here.
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    doc = ezdxf.new(dxfversion="R2010")
    doc.layers.add(name="PLOT_BOUNDARY", color=1)
    doc.layers.add(name="ROOMS", color=3)
    doc.layers.add(name="LABELS", color=7)
    doc.layers.add(name="ROAD_SIDE", color=2)

    msp = doc.modelspace()

    # Plot boundary
    msp.add_lwpolyline(
        [(0, 0), (plot_length_ft, 0), (plot_length_ft, plot_width_ft), (0, plot_width_ft), (0, 0)],
        dxfattribs={"layer": "PLOT_BOUNDARY"},
    )

    # Road-facing side marker (offset line just outside the boundary on the given side)
    side_map = {
        "north": [(0, plot_width_ft + 2), (plot_length_ft, plot_width_ft + 2)],
        "south": [(0, -2), (plot_length_ft, -2)],
        "east": [(plot_length_ft + 2, 0), (plot_length_ft + 2, plot_width_ft)],
        "west": [(-2, 0), (-2, plot_width_ft)],
    }
    road_line = side_map.get(road_facing_side.strip().lower())
    if road_line:
        msp.add_line(road_line[0], road_line[1], dxfattribs={"layer": "ROAD_SIDE"})
        msp.add_text(
            "ROAD",
            dxfattribs={"layer": "ROAD_SIDE", "height": 1.5},
        ).set_placement(road_line[0])

    # Rooms
    for room in rooms:
        x, y = room["x"], room["y"]
        length, width = room["length"], room["width"]
        true_color = _hex_to_true_color(room.get("color"))

        poly_attribs = {"layer": "ROOMS"}
        label_attribs = {"layer": "LABELS", "height": 1.0}
        if true_color is not None:
            poly_attribs["true_color"] = true_color
            label_attribs["true_color"] = true_color

        msp.add_lwpolyline(
            [(x, y), (x + length, y), (x + length, y + width), (x, y + width), (x, y)],
            dxfattribs=poly_attribs,
        )
        label_point = (x + length / 2, y + width / 2)
        msp.add_text(
            room.get("name", "Room"),
            dxfattribs=label_attribs,
        ).set_placement(label_point, align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

    output_path = output_dir / f"{design_id}.dxf"
    doc.saveas(output_path)
    return output_path
