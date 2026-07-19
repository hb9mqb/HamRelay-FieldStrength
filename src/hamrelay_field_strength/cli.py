from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import CalculationRequest
from .propagation import calculate
from .tiles import write_pyramid


def main() -> None:
    parser = argparse.ArgumentParser(prog="hamrelay-field-strength")
    commands = parser.add_subparsers(dest="command", required=True)
    calculate_parser = commands.add_parser("calculate", help="calculate a field-strength raster")
    calculate_parser.add_argument("--config", type=Path, required=True)
    tiles_parser = commands.add_parser("tiles", help="build color and numeric tile pyramids")
    tiles_parser.add_argument("--geotiff", type=Path, required=True)
    tiles_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "calculate":
        request = CalculationRequest.model_validate_json(args.config.read_text(encoding="utf-8"))
        result = calculate(request)
        print(
            json.dumps(
                {"field_geotiff": str(result.field_geotiff), "manifest": str(result.manifest)}
            )
        )
    else:
        print(json.dumps({"tiles": write_pyramid(args.geotiff, args.output)}))


if __name__ == "__main__":
    main()
