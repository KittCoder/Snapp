from __future__ import annotations

import argparse
import json
from pathlib import Path

from model import (
    SCRAPED_GROCERY_DB_FILENAME,
    SALE_INGREDIENT_CANDIDATES_FILENAME,
    write_sale_candidate_artifact,
)


MODEL_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE = MODEL_DIR / SCRAPED_GROCERY_DB_FILENAME
DEFAULT_OUTPUT = MODEL_DIR / SALE_INGREDIENT_CANDIDATES_FILENAME


def main() -> None:
    parser = argparse.ArgumentParser(description="Build cached sale ingredient candidates.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    payload = write_sale_candidate_artifact(args.output, source_path=args.source)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "candidate_count": len(payload.get("candidates") or []),
                "exclusion_sample_count": len(payload.get("exclusions") or []),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
