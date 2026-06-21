import json
from dataclasses import asdict


def render_json(
    assessment
) -> str:

    return json.dumps(
        asdict(assessment),
        indent=4
    )