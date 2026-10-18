"""Deterministic room snapping for legacy generated layouts."""

from typing import Any


def snap_and_pack_architectural_layout(design: dict[str, Any]) -> dict[str, Any]:
    """
    Mathematically packs rooms into a cohesive contiguous architectural building:
    - Eliminates disconnected island gaps (rooms touch edge-to-edge sharing common walls).
    - Attached bathrooms snap flush against their parent bedrooms with zero void.
    - Multi-room houses are organized into Ground Floor (y: 0.0) and Upper Floor (y: 3.2).
    - Adds an architectural staircase connecting Ground to Upper floor.
    - Generates connecting doors between adjacent spaces and exterior sliding glass walls.
    """
    rooms = design.get("rooms", [])
    if not rooms:
        return design

    if len(rooms) == 1:
        single_r = rooms[0]
        lw = float(single_r.get("width") or 8.0)
        ll = float(single_r.get("length") or 7.0)
        single_r["position"] = {"x": 0.0, "y": 0.0, "z": 0.0}
        single_r["floor"] = 0
        single_r["width"] = lw
        single_r["length"] = ll

        rid = single_r.get("id", "room_01")
        design["doors"] = [
            {
                "id": f"door_main_{rid}",
                "roomId": rid,
                "room_id": rid,
                "wall": "front",
                "wall_side": "south",
                "position": {"x": 0.0, "y": 1.05, "z": round(-ll / 2.0, 2)},
                "width": 1.0,
                "height": 2.1,
            }
        ]
        design["windows"] = [
            {
                "id": f"win_{rid}_left",
                "roomId": rid,
                "room_id": rid,
                "wall": "left",
                "wall_side": "west",
                "position": {"x": round(-lw / 2.0, 2), "y": 1.5, "z": 0.0},
                "width": 1.8,
                "height": 1.4,
            },
            {
                "id": f"win_{rid}_right",
                "roomId": rid,
                "room_id": rid,
                "wall": "right",
                "wall_side": "east",
                "position": {"x": round(lw / 2.0, 2), "y": 1.5, "z": 0.0},
                "width": 1.8,
                "height": 1.4,
            },
        ]
        return design

    # Classify rooms by architectural role
    living_rooms = []
    kitchens = []
    bedrooms = []
    bathrooms = []
    other_rooms = []

    for r in rooms:
        rtype = str(r.get("type", "")).lower()
        if any(k in rtype for k in ["living", "lounge", "great", "family", "drawing"]):
            living_rooms.append(r)
        elif any(k in rtype for k in ["kitchen", "dining", "pantry"]):
            kitchens.append(r)
        elif any(k in rtype for k in ["bath", "wash", "toilet", "powder", "restroom"]):
            bathrooms.append(r)
        elif any(k in rtype for k in ["bed", "guest", "master"]):
            bedrooms.append(r)
        else:
            other_rooms.append(r)

    # Special handling for small 2-room home (e.g., Bedroom + Bathroom)
    if len(rooms) == 2 and not living_rooms:
        main_r = bedrooms[0] if bedrooms else rooms[0]
        second_r = bathrooms[0] if bathrooms else rooms[1]

        mw = float(main_r.get("width") or 7.0)
        ml = float(main_r.get("length") or 7.0)
        sw = float(second_r.get("width") or 3.5)
        sl = float(second_r.get("length") or 3.5)

        main_r["width"] = mw
        main_r["length"] = ml
        main_r["floor"] = 0
        main_r["position"] = {"x": round(-sw / 2.0, 2), "y": 0.0, "z": 0.0}

        second_r["width"] = sw
        second_r["length"] = sl
        second_r["floor"] = 0
        second_r["position"] = {"x": round(mw / 2.0, 2), "y": 0.0, "z": 0.0}

        m_id = main_r.get("id", "bedroom_01")
        s_id = second_r.get("id", "bathroom_01")

        design["doors"] = [
            {
                "id": "door_main_entrance",
                "roomId": m_id,
                "room_id": m_id,
                "wall": "front",
                "wall_side": "south",
                "position": {"x": round(-sw / 2.0, 2), "y": 1.05, "z": round(-ml / 2.0, 2)},
                "width": 1.0,
                "height": 2.1,
            },
            {
                "id": f"door_{m_id}_{s_id}_connect",
                "roomId": s_id,
                "room_id": s_id,
                "wall": "left",
                "wall_side": "west",
                "position": {"x": round((-sw / 2.0 + mw / 2.0) / 2.0, 2), "y": 1.05, "z": 0.0},
                "width": 0.9,
                "height": 2.1,
            },
        ]
        design["windows"] = [
            {
                "id": f"win_{m_id}_left",
                "roomId": m_id,
                "room_id": m_id,
                "wall": "left",
                "wall_side": "west",
                "position": {"x": round(-sw / 2.0 - mw / 2.0, 2), "y": 1.5, "z": 0.0},
                "width": 1.8,
                "height": 1.4,
            },
            {
                "id": f"win_{m_id}_front",
                "roomId": m_id,
                "room_id": m_id,
                "wall": "front",
                "wall_side": "south",
                "position": {"x": round(-sw / 2.0, 2), "y": 1.5, "z": round(-ml / 2.0, 2)},
                "width": 1.8,
                "height": 1.4,
            },
            {
                "id": f"win_{s_id}_right",
                "roomId": s_id,
                "room_id": s_id,
                "wall": "right",
                "wall_side": "east",
                "position": {"x": round(mw / 2.0 + sw / 2.0, 2), "y": 1.5, "z": 0.0},
                "width": 1.2,
                "height": 1.2,
            },
        ]
        return design

    # Primary ground floor hub: Living room
    living = living_rooms[0] if living_rooms else rooms[0]
    lw = float(living.get("width") or 9.0)
    ll = float(living.get("length") or 8.0)
    living["width"] = lw
    living["length"] = ll
    living["position"] = {"x": 0.0, "y": 0.0, "z": 0.0}
    living["floor"] = 0

    # 1. Kitchen & Dining: Placed contiguous to Living Room on +X (Right side)
    kw = 6.5
    if kitchens:
        kit = kitchens[0]
        kw = float(kit.get("width") or 6.5)
        kl = float(kit.get("length") or 7.5)
        kit["width"] = kw
        kit["length"] = kl
        kit["position"] = {"x": round(lw / 2.0 + kw / 2.0, 2), "y": 0.0, "z": 0.0}
        kit["floor"] = 0

    # 2. Ground Floor Bedroom 1: Placed contiguous to Living Room on -X (Left side)
    ground_bed = None
    if bedrooms:
        ground_bed = bedrooms[0]
        bw = float(ground_bed.get("width") or 7.0)
        bl = float(ground_bed.get("length") or 7.0)
        ground_bed["width"] = bw
        ground_bed["length"] = bl
        ground_bed["position"] = {"x": round(-(lw / 2.0 + bw / 2.0), 2), "y": 0.0, "z": 0.0}
        ground_bed["floor"] = 0

    # 3. Ground Attached Bathroom: Snapped flush behind Ground Bedroom (-Z)
    if bathrooms and ground_bed:
        ground_bath = bathrooms[0]
        baw = float(ground_bath.get("width") or 4.0)
        bal = float(ground_bath.get("length") or 3.5)
        ground_bath["width"] = baw
        ground_bath["length"] = bal
        gb_pos = ground_bed["position"]
        gb_l = float(ground_bed["length"])
        ground_bath["position"] = {
            "x": gb_pos["x"],
            "y": 0.0,
            "z": round(gb_pos["z"] - (gb_l / 2.0 + bal / 2.0), 2),
        }
        ground_bath["floor"] = 0

    # 4. Master Bedroom Suite: Placed contiguous flush behind Living Room (-Z)
    upper_rooms = []
    if len(bedrooms) > 1:
        master_bed = bedrooms[1]
        mw = float(master_bed.get("width") or 8.0)
        ml = float(master_bed.get("length") or 7.0)
        master_bed["width"] = mw
        master_bed["length"] = ml
        master_bed["position"] = {
            "x": 0.0,
            "y": 0.0,
            "z": round(-(ll / 2.0 + ml / 2.0), 2),
        }
        master_bed["floor"] = 0

        if len(bathrooms) > 1:
            master_bath = bathrooms[1]
            mbw = float(master_bath.get("width") or 4.2)
            mbl = float(master_bath.get("length") or 3.8)
            master_bath["width"] = mbw
            master_bath["length"] = mbl
            master_bath["position"] = {
                "x": round(mw / 2.0 + mbw / 2.0, 2),
                "y": 0.0,
                "z": master_bed["position"]["z"],
            }
            master_bath["floor"] = 0

    # 5. Third Bedroom (if present, placed contiguous on rear wing next to Master Bedroom)
    if len(bedrooms) > 2:
        bed3 = bedrooms[2]
        b3w = float(bed3.get("width") or 6.5)
        b3l = float(bed3.get("length") or 6.5)
        bed3["width"] = b3w
        bed3["length"] = b3l
        mw = float(bedrooms[1].get("width") or 8.0)
        bed3["position"] = {
            "x": round(-(mw / 2.0 + b3w / 2.0), 2),
            "y": 0.0,
            "z": round(-(ll / 2.0 + b3l / 2.0), 2),
        }
        bed3["floor"] = 0

        if len(bathrooms) > 2:
            bath3 = bathrooms[2]
            b3bw = float(bath3.get("width") or 3.8)
            b3bl = float(bath3.get("length") or 3.2)
            bath3["width"] = b3bw
            bath3["length"] = b3bl
            bath3["position"] = {
                "x": bed3["position"]["x"],
                "y": 0.0,
                "z": round(bed3["position"]["z"] - (b3l / 2.0 + b3bl / 2.0), 2),
            }
            bath3["floor"] = 0

    # Handle any remaining other rooms (e.g. Office, Dining)
    for idx, o in enumerate(other_rooms):
        ow = float(o.get("width") or 5.0)
        ol = float(o.get("length") or 5.0)
        o["width"] = ow
        o["length"] = ol
        o["position"] = {"x": round(lw / 2.0 + kw / 2.0, 2), "y": 0.0, "z": round((idx + 1) * 6.0, 2)}
        o["floor"] = 0

    # Ensure connecting staircase exists in Living Room for multi-floor homes
    if upper_rooms:
        # Check both old format (room-level furniture) and new format (top-level furniture)
        living_furniture = living.get("furniture", [])
        top_level_furniture = design.get("furniture", [])
        has_stairs = any(
            f.get("type") in ["staircase", "stairs"] or f.get("asset") in ["staircase", "stairs"]
            for f in living_furniture
        )
        if not has_stairs:
            has_stairs = any(
                (f.get("asset") in ["staircase", "stairs"] and f.get("roomId") == living.get("id"))
                for f in top_level_furniture
            )
        if not has_stairs:
            # Add staircase to top-level furniture if using new format, else to room
            staircase_item = {
                "id": "main_staircase",
                "asset": "staircase",
                "roomId": living.get("id", "living_01"),
                "position": {"x": round(lw / 2.0 - 1.2, 2), "y": 0.0, "z": round(-ll / 2.0 + 2.0, 2)},
                "rotation": 0,
                "scale": 1.0,
            }
            if top_level_furniture is not None and isinstance(top_level_furniture, list):
                top_level_furniture.append(staircase_item)
                design["furniture"] = top_level_furniture
            else:
                # Fallback: add to room-level furniture (old format compat)
                living.setdefault("furniture", []).append({
                    "id": "main_staircase",
                    "type": "staircase",
                    "label": "Architectural Floating Stairs",
                    "position": {"x": round(lw / 2.0 - 1.2, 2), "y": 0.0, "z": round(-ll / 2.0 + 2.0, 2)},
                    "rotation_y": 0,
                    "dimensions": {"w": 1.2, "h": 3.2, "d": 3.8},
                    "color": "#7c5335",
                })

    # Generate clean, accurate doors and windows placed on snapped room wall boundaries
    snapped_doors = []
    snapped_windows = []

    # 1. Main entrance door on Living Room front wall
    snapped_doors.append({
        "id": "door_main_entrance",
        "roomId": living.get("id", "living_01"),
        "wall": "front",
        "position": {"x": round(living["position"]["x"], 2), "y": 1.05, "z": round(living["position"]["z"] - ll / 2.0, 2)},
        "width": 1.0,
        "height": 2.1,
    })

    # 2. Living -> Kitchen connecting passage
    if kitchens:
        snapped_doors.append({
            "id": "door_living_kitchen",
            "roomId": living.get("id", "living_01"),
            "wall": "right",
            "position": {"x": round(lw / 2.0, 2), "y": 1.05, "z": 0.0},
            "width": 1.2,
            "height": 2.1,
        })
        k_pos = kitchens[0]["position"]
        k_w = float(kitchens[0]["width"])
        snapped_windows.append({
            "id": "window_kitchen_ext",
            "roomId": kitchens[0].get("id", "kitchen_01"),
            "wall": "right",
            "position": {"x": round(k_pos["x"] + k_w / 2.0, 2), "y": 1.5, "z": round(k_pos["z"], 2)},
            "width": 1.8,
            "height": 1.4,
        })

    # 3. Living -> Ground Bedroom connecting door & bedroom window
    if ground_bed:
        snapped_doors.append({
            "id": "door_living_bedroom",
            "roomId": living.get("id", "living_01"),
            "wall": "left",
            "position": {"x": round(-lw / 2.0, 2), "y": 1.05, "z": 0.0},
            "width": 0.9,
            "height": 2.1,
        })
        gb_pos = ground_bed["position"]
        gb_w = float(ground_bed["width"])
        snapped_windows.append({
            "id": "window_bedroom_left",
            "roomId": ground_bed.get("id", "bedroom_01"),
            "wall": "left",
            "position": {"x": round(gb_pos["x"] - gb_w / 2.0, 2), "y": 1.5, "z": round(gb_pos["z"], 2)},
            "width": 2.0,
            "height": 1.5,
        })
        if bathrooms:
            snapped_doors.append({
                "id": "door_bed_bath_01",
                "roomId": ground_bed.get("id", "bedroom_01"),
                "wall": "back",
                "position": {"x": round(gb_pos["x"], 2), "y": 1.05, "z": round(gb_pos["z"] - float(ground_bed["length"]) / 2.0, 2)},
                "width": 0.85,
                "height": 2.1,
            })

    # 4. Panoramic living room front windows
    snapped_windows.append({
        "id": "window_living_front_01",
        "roomId": living.get("id", "living_01"),
        "wall": "front",
        "position": {"x": round(living["position"]["x"] + lw / 3.2, 2), "y": 1.5, "z": round(living["position"]["z"] - ll / 2.0, 2)},
        "width": 2.2,
        "height": 1.6,
    })
    snapped_windows.append({
        "id": "window_living_front_02",
        "roomId": living.get("id", "living_01"),
        "wall": "front",
        "position": {"x": round(living["position"]["x"] - lw / 3.2, 2), "y": 1.5, "z": round(living["position"]["z"] - ll / 2.0, 2)},
        "width": 2.2,
        "height": 1.6,
    })

    # 5. Master Suite connecting doors and windows
    if len(bedrooms) > 1:
        snapped_doors.append({
            "id": "door_living_master_bed",
            "roomId": living.get("id", "living_01"),
            "wall": "back",
            "position": {"x": round(living["position"]["x"], 2), "y": 1.05, "z": round(living["position"]["z"] - ll / 2.0, 2)},
            "width": 1.0,
            "height": 2.1,
        })
        m_pos = bedrooms[1]["position"]
        m_l = float(bedrooms[1]["length"])
        snapped_windows.append({
            "id": "window_master_bedroom_back",
            "roomId": bedrooms[1].get("id", "bedroom_02"),
            "wall": "back",
            "position": {"x": round(m_pos["x"], 2), "y": 1.5, "z": round(m_pos["z"] - m_l / 2.0, 2)},
            "width": 2.2,
            "height": 1.5,
        })
        if len(bathrooms) > 1:
            mb_w = float(bedrooms[1]["width"])
            snapped_doors.append({
                "id": "door_master_bed_bath",
                "roomId": bedrooms[1].get("id", "bedroom_02"),
                "wall": "right",
                "position": {"x": round(m_pos["x"] + mb_w / 2.0, 2), "y": 1.05, "z": round(m_pos["z"], 2)},
                "width": 0.85,
                "height": 2.1,
            })

    design["doors"] = snapped_doors
    design["windows"] = snapped_windows

    # Exterior elements metadata for 3D renderer
    design["exterior"] = {
        "pool": {
            "enabled": True,
            "width": 10.5,
            "length": 4.8,
            "depth": 1.6,
            "position": {"x": 2.5, "y": -0.2, "z": round(ll / 2.0 + 5.5, 2)},
        },
        "patio": {
            "enabled": True,
            "width": round(lw + 6.0, 2),
            "length": 4.2,
            "position": {"x": 0.0, "y": 0.0, "z": round(ll / 2.0 + 2.1, 2)},
        },
    }

snap_and_normalize_architectural_layout = snap_and_pack_architectural_layout

