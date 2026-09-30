"""Part-owned neural task contracts; shared core provides only safe loading/kernel."""
from importlib import import_module

PARTS = tuple(f"part{i}_" + name for i, name in enumerate((
    "breakout", "zone", "psychology", "volume", "ml", "trend",
    "volatility", "structure", "orderflow", "candlestats", "fusion", "confidence"), 1))
TASKS = {part: import_module(f"{__name__}.part{i}") for i, part in enumerate(PARTS, 1)}
FEATURE_NAMES = {part: TASKS[part].FEATURE_NAMES for part in PARTS}
MODEL_SPECS = {part: TASKS[part].MODEL_SPEC for part in PARTS}


def prepare_features(part_id, data):
    try:
        module = TASKS[part_id]
    except KeyError as exc:
        raise ValueError("unknown_part_id") from exc
    return tuple(module.prepare_features(data))


def label_target(part_id, rows, index, horizon, neutral_bps, features):
    try:
        module = TASKS[part_id]
    except KeyError as exc:
        raise ValueError("unknown_part_id") from exc
    return module.label_target(rows, index, horizon, neutral_bps, features)
