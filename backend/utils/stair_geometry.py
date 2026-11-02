"""Stair geometry shared by generation and architectural preflight.

Dimensions describe the axis-aligned footprint. ``steps``/``risers`` count
vertical increments, and the renderer draws that many tread modules (including
the module meeting each landing). These are project design targets in metres.
"""

from __future__ import annotations

import math

MIN_CLEAR_WIDTH = 0.90
MIN_TREAD_DEPTH = 0.25
MAX_RISER_HEIGHT = 0.19
TARGET_RISER_HEIGHT = 0.175
CENTRAL_GAP = 0.16
MIN_STEPS = 16


def number(value, default=0.0):
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def default_risers(rise=3.0):
    return max(MIN_STEPS, math.ceil(number(rise, 3.0) / TARGET_RISER_HEIGHT / 2 - 1e-9) * 2)


def minimum_stair_dimensions(stair_type="u_shaped", rise=3.0, clear_width=1.0, landing_depth=None):
    """Return the smallest footprint meeting the renderer's tread convention."""
    clear = max(MIN_CLEAR_WIDTH, number(clear_width, 1.0))
    landing = max(0.9, clear, number(landing_depth))
    steps = default_risers(rise)
    if stair_type == "straight":
        width, depth = clear, landing + steps * MIN_TREAD_DEPTH
    elif stair_type == "l_shaped":
        width = depth = landing + steps / 2 * MIN_TREAD_DEPTH
    else:
        width, depth = 2 * clear + CENTRAL_GAP, landing + steps / 2 * MIN_TREAD_DEPTH
    return {"width": round(width, 4), "depth": round(depth, 4), "height": number(rise, 3.0),
            "steps": steps, "risers": steps, "clear_width": clear, "landing_depth": landing}


def stair_metrics(stair, rise=None):
    """Calculate the geometry actually rendered and explain invalid parameters.

    An explicit impossible count is reported, even though ``steps`` in the
    returned metrics follows the renderer's even/minimum-count normalization.
    This prevents a false pass based on a claimed, unbuildable step count.
    """
    dimensions = stair.get("dimensions") or {}
    width, depth = number(dimensions.get("width")), number(dimensions.get("depth"))
    world_width, world_depth = width, depth
    run_axis = stair.get("run_axis", "y")
    if run_axis == "x":
        width, depth = depth, width
    height = number(rise, number(dimensions.get("height"), 3.0))
    kind = str(stair.get("type") or stair.get("configuration") or "u_shaped")
    if kind == "stair_void":
        kind = str(stair.get("source_stair_type") or stair.get("configuration") or "u_shaped")
    raw_steps = stair.get("steps", stair.get("risers", default_risers(height)))
    count = number(raw_steps)
    steps = max(MIN_STEPS, int(count))
    steps += steps % 2
    errors = []
    if run_axis not in ("x", "y"):
        errors.append("has an unsupported run axis.")
    if run_axis == "x" and kind != "u_shaped":
        errors.append("supports the across-plot direction for U-shaped stairs only.")

    def explicit_number(key, fallback):
        value = stair.get(key)
        if value is None:
            return fallback
        try:
            # Match the editor's Number() handling of numeric strings,
            # including an empty/whitespace string becoming zero.
            parsed = 0.0 if isinstance(value, str) and not value.strip() else float(value)
            if math.isfinite(parsed):
                return parsed
        except (TypeError, ValueError):
            pass
        errors.append(f"has an invalid {key}; use a finite number.")
        return fallback

    if kind not in ("straight", "l_shaped", "u_shaped"):
        errors.append("has an unsupported stair type.")
    if width <= 0 or depth <= 0 or height <= 0:
        errors.append("needs positive footprint dimensions and floor-to-floor rise.")
    if count < MIN_STEPS or count != int(count) or count % 2:
        errors.append("needs an even integer riser count of at least 16.")
    if "steps" in stair and "risers" in stair and number(stair["steps"]) != number(stair["risers"]):
        errors.append("has inconsistent steps and risers counts.")
    actual_width = (width - CENTRAL_GAP) / 2 if kind == "u_shaped" else width
    default_clear = actual_width if kind == "u_shaped" else min(width, 1.1)
    stated_clear = explicit_number("clear_width", default_clear)
    clear = min(stated_clear, actual_width)
    landing = explicit_number("landing_depth", max(0.9, stated_clear))
    if kind == "l_shaped":
        actual_width = min(width, depth, stated_clear)
        clear = min(stated_clear, actual_width)
        tread = min(width - landing, depth - landing) / (steps / 2)
    else:
        tread = (depth - landing) / (steps if kind == "straight" else steps / 2)
    if clear < MIN_CLEAR_WIDTH - 1e-6:
        errors.append("is narrower than 0.90 m clear width.")
    if actual_width < stated_clear - 1e-6:
        errors.append("has a footprint too narrow for its declared clear width.")
    if landing < max(0.9, stated_clear) - 1e-6:
        errors.append("needs a landing at least as deep as the clear flight width (minimum 0.90 m).")
    access = explicit_number("access_depth", clear)
    if stair.get("access_depth") is not None and access < clear - 1e-6:
        errors.append("needs clear floor access at least as deep as the clear flight width.")
    if tread < MIN_TREAD_DEPTH - 1e-6:
        errors.append(f"has a stair run too short: {max(0.0, tread):.3f} m per tread; allow at least 0.25 m.")
    riser_height = height / steps
    if riser_height > MAX_RISER_HEIGHT + 1e-6:
        errors.append(f"has {riser_height:.3f} m risers; increase the riser count to keep risers at or below 0.19 m.")
    if abs(explicit_number("rotation", 0.0) % 360) > 1e-6:
        errors.append("uses an unsupported rotation; stairs must use their axis-aligned footprint.")
    return {"type": kind, "width": world_width, "depth": world_depth, "local_width": width, "local_depth": depth, "run_axis": run_axis, "height": height,
            "steps": steps, "risers": steps, "riser_height": riser_height,
            "tread_depth": tread, "clear_width": clear, "flight_width": actual_width,
            "landing_depth": landing, "errors": errors}


def stair_approach_box(stair, upper=False):
    """Return the clear floor landing outside the stair/void, in world XY."""
    metrics = stair_metrics(stair)
    position = stair.get("position") or {}
    x, y = number(position.get("x")), number(position.get("y"))
    width, depth, clear = metrics["width"], metrics["depth"], metrics["clear_width"]
    access = max(clear, number(stair.get("access_depth"), clear))
    if metrics["run_axis"] == "x":
        return x + width, y, x + width + access, y + depth
    if upper and metrics["type"] == "straight":
        return x, y + depth, x + width, y + depth + access
    if upper and metrics["type"] == "l_shaped":
        return x + width, y + depth - clear, x + width + access, y + depth
    return x, y - access, x + (clear if metrics["type"] == "l_shaped" else width), y
