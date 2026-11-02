"""A circulation-first arrangement for narrow, two-storey family homes.

This is a bounded planning alternative to the shelf packer, not permission to
enlarge the site or relax stair geometry. Dimensions remain canonical metres.
"""

from collections import Counter
from utils.stair_geometry import minimum_stair_dimensions


COMPACT_ROOM_DIMENSIONS = {
    "living_room": (2.8, 3.0), "dining_room": (1.8, 2.0),
    "kitchen": (2.4, 2.4), "bedroom": (2.8, 2.8),
    "bathroom": (1.5, 2.0), "balcony": (1.5, 2.0),
    "stair_lobby": (2.6, 4.6),
}


def plan_compact_home(engine, groups, width, depth, x0, y0, rise, orientation):
    """Return a paired plan only for a program this arrangement can satisfy."""
    expected = [Counter(living_room=1, dining_room=1, kitchen=1, bedroom=1, bathroom=1),
                Counter(bedroom=2, bathroom=1, living_room=1, balcony=1)]
    if len(groups) != 2 or orientation != "north" or not (6.10 <= width <= 6.80 and 8.50 <= depth <= 11):
        return None
    for group, counts in zip(groups, expected):
        if Counter(room["type"] for room in group if room["type"] != "stair_lobby") != counts:
            return None
    # Across the plot, the turn landing and two nine-module flights occupy
    # 3.25 m; the east end has 1.20 m clear floor access. Bathrooms stack in
    # the remaining east strip. No requested setback is changed.
    stair = minimum_stair_dimensions("u_shaped", rise=rise, clear_width=1.0)
    if stair["depth"] > 3.25 or stair["width"] > 2.20:
        return None
    lobby_w, lobby_d, split = 4.60, 2.60, round(width / 2, 2)
    ground_mid = round(depth - lobby_d - 3.10, 2)
    upper_mid = round((depth - lobby_d) / 2, 2)
    rectangles = [
        [("stair_lobby", 0, 0, lobby_w, lobby_d),
         ("bathroom", lobby_w, 0, width-lobby_w, lobby_d),
         ("bedroom", 0, lobby_d, split, ground_mid),
         ("kitchen", split, lobby_d, width-split, ground_mid),
         ("living_room", 0, lobby_d+ground_mid, 3.60, 3.10),
         ("dining_room", 3.60, lobby_d+ground_mid, width-3.60, 3.10)],
        [("stair_lobby", 0, 0, lobby_w, lobby_d),
         ("bathroom", lobby_w, 0, width-lobby_w, lobby_d),
         ("bedroom", 0, lobby_d, split, upper_mid),
         ("bedroom", 0, lobby_d+upper_mid, split, depth-lobby_d-upper_mid),
         ("living_room", split, lobby_d, width-split, depth-lobby_d-1.50),
         ("balcony", split, depth-1.50, width-split, 1.50)],
    ]
    floors = []
    for level, specs in enumerate(rectangles):
        available = list(groups[level])
        rooms = []
        for kind, x, y, w, d in specs:
            source = next(room for room in available if room["type"] == kind)
            available.remove(source)
            raw = source.get("raw", {})
            room = engine._create_room_dict(
                room_id=raw.get("id", f"compact_{kind}_{level}_{len(rooms)}"),
                name=source["name"], room_type=kind, x=x0+x, y=y0+y,
                z=level*rise, w=w, d=d, materials=engine._default_materials(kind), floor_idx=level,
            )
            room["layout_profile"] = "compact_residential"
            if kind == "bedroom" and level == 0:
                room["name"], room["bed_size"] = "Guest Bedroom", "single"
            if kind == "living_room" and level == 1:
                room["name"] = "Family Lounge"
            if kind == "balcony":
                room["open_air"] = True
            rooms.append(room)
        engine._copy_requested_room_metadata(rooms, groups[level])
        # This arrangement implements shared bathrooms. Unsolicited ensuite
        # relationships in an LLM response must not contradict that program.
        for room in rooms:
            room.pop("ensuite_id", None)
            room.pop("ensuite_for_room_id", None)
            if room["type"] == "bathroom":
                room["access"] = "shared"
        engine._namespace_floor_room_ids(rooms, level)
        floors.append(rooms)
    core = {
        "position": {"x": round(x0+.15, 2), "y": round(y0+.20, 2), "z": 0},
        "dimensions": {"width": 3.25, "depth": 2.20, "height": rise},
        "opening_dimensions": {"width": 3.30, "depth": 2.25},
        "opening_clearance": .05,
        "type": "u_shaped", "configuration": "u_shaped", "run_axis": "x",
        "steps": stair["steps"], "risers": stair["steps"], "riser": rise/stair["steps"],
        "tread": .25, "landing_depth": 1.0, "clear_width": 1.0,
        "access_depth": 1.15, "headroom": 2.10,
        "room_ids_by_level": {str(i): next(r["id"] for r in rooms if r["type"] == "stair_lobby")
                              for i, rooms in enumerate(floors)},
    }
    return floors, core
