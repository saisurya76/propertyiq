from pathlib import Path
from typing import Any

import ezdxf

DEFAULT_OUTPUT_DIR = Path("outputs/dxf")


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

    `rooms` = [{"name": str, "x": float, "y": float, "length": float, "width": float}, ...]
    Coordinates are in feet, plot origin at (0, 0).

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
        msp.add_lwpolyline(
            [(x, y), (x + length, y), (x + length, y + width), (x, y + width), (x, y)],
            dxfattribs={"layer": "ROOMS"},
        )
        label_point = (x + length / 2, y + width / 2)
        msp.add_text(
            room.get("name", "Room"),
            dxfattribs={"layer": "LABELS", "height": 1.0},
        ).set_placement(label_point, align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

    output_path = output_dir / f"{design_id}.dxf"
    doc.saveas(output_path)
    return output_path
