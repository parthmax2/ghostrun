"""Shared dataset loading/splitting for the ghostrun-vs-DSPy benchmark.

Fixed positional split (not random) so both tools train on exactly the same
25 rows and get evaluated on exactly the same 15 held-out rows neither tool
ever sees during training.
"""

import json
from pathlib import Path

DATASET_PATH = Path(__file__).parent / "dataset.jsonl"
CATEGORIES = ["billing", "technical", "account", "general"]
URGENCIES = ["low", "medium", "high"]


def load_rows():
    rows = []
    with DATASET_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def split():
    rows = load_rows()
    train, test = rows[:25], rows[25:]
    assert len(test) == 15, f"expected 15 held-out rows, got {len(test)}"
    return train, test
