"""Parse exact room counts assigned to individual building floors."""

from __future__ import annotations

import re
from typing import Dict, Optional


NUMBER_WORDS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

ROOM_ALIASES = {
    "master bedroom": "master_bedroom",
    "master bed room": "master_bedroom",
    "guest bedroom": "bedroom",
    "guest bed room": "bedroom",
    "bedroom": "bedroom",
    "bed room": "bedroom",
    "bathroom": "bathroom",
    "bath room": "bathroom",
    "washroom": "bathroom",
    "wash room": "bathroom",
    "toilet": "bathroom",
    "living room": "living_room",
    "family lounge": "living_room",
    "lounge": "living_room",
    "kitchen": "kitchen",
    "dining room": "dining_room",
    "dining area": "dining_room",
    "home office": "home_office",
    "office": "home_office",
    "study": "home_office",
    "garage": "garage",
    "foyer": "foyer",
    "corridor": "corridor",
    "hallway": "corridor",
    "laundry": "laundry",
    "balcony": "balcony",
    "terrace": "terrace",
}

COUNT_TOKEN = r"(?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
ROOM_TOKEN = "|".join(
    sorted((re.escape(name) + "s?" for name in ROOM_ALIASES), key=len, reverse=True)
)
FLOOR_TOKEN = (
    r"(?:ground(?:\s+(?:floor|level|storey|story))?"
    r"|first(?:\s+(?:floor|level|storey|story))?"
    r"|second(?:\s+(?:floor|level|storey|story))?"
    r"|third(?:\s+(?:floor|level|storey|story))?"
    r"|[0-3](?:st|nd|rd|th)?(?:\s+(?:floor|level|storey|story))?"
    r"|(?:floor|level|storey|story)\s*[0-3])"
)


def floor_level(value: str) -> Optional[int]:
    """Translate a natural-language floor label to the canonical zero-based level."""
    text = re.sub(r"\s+", " ", str(value or "").strip().lower())
    if re.search(r"\bground\b", text):
        return 0
    word_levels = {"first": 1, "second": 2, "third": 3}
    for word, level in word_levels.items():
        if re.search(rf"\b{word}\b", text):
            return level
    match = re.search(r"\b([0-3])(?:st|nd|rd|th)?\b", text)
    return int(match.group(1)) if match else None


def _count(value: str) -> int:
    value = str(value).lower()
    return NUMBER_WORDS.get(value, int(value) if value.isdigit() else 1)


def _room_type(value: str) -> Optional[str]:
    clean = re.sub(r"\s+", " ", value.lower().strip())
    if clean.endswith("s"):
        clean = clean[:-1]
    return ROOM_ALIASES.get(clean)


def _section_room_counts(text: str) -> Dict[int, Dict[str, int]]:
    """Read enumerated room lists under explicit floor headings.

    Headings establish the floor for every comma-separated room, including
    singular rooms without a numeral and adjectives such as ``shared``. Stop
    at the end of the list's sentence so subsequent design instructions do not
    accidentally become additional room requirements.
    """
    headings = list(re.finditer(
        rf"\b(?P<floor>{FLOOR_TOKEN})\s*[:\u2014\u2013]\s*",
        text,
        re.IGNORECASE,
    ))
    result: Dict[int, Dict[str, int]] = {}
    room_pattern = re.compile(
        rf"^\s*(?:(?P<count>{COUNT_TOKEN})\s+)?"
        rf"(?:(?:small|compact|shared|family|front|rear|large|main|common|guest)\s+)*"
        rf"(?P<room>{ROOM_TOKEN})\b",
        re.IGNORECASE,
    )
    for index, heading in enumerate(headings):
        level = floor_level(heading.group("floor"))
        if level is None:
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = re.split(r"(?<!\d)\.(?:\s|$)|[\r\n]", text[heading.end():end], maxsplit=1)[0]
        counts: Dict[str, int] = {}
        for clause in re.split(r"\s*(?:,|;|\band\b|&)\s*", body):
            match = room_pattern.match(clause.strip())
            room_type = _room_type(match.group("room")) if match else None
            if room_type:
                counts[room_type] = counts.get(room_type, 0) + _count(match.group("count") or "one")
        if counts:
            result.setdefault(level, {}).update(counts)
    return result


def parse_floor_room_counts(prompt: str) -> Dict[int, Dict[str, int]]:
    """Return exact per-floor room counts from independent prompt clauses.

    A later clause may omit the room name (``and 2 on first floor``); in that
    case it inherits the most recently stated room type.
    """
    raw_text = str(prompt or "").lower()
    text = re.sub(r"\s+", " ", raw_text).strip()
    if not text:
        return {}

    clauses = [part.strip() for part in re.split(r"\s*(?:,|;|\band\b|&)\s*", text) if part.strip()]
    result: Dict[int, Dict[str, int]] = {}
    inherited_room: Optional[str] = None

    direct = re.compile(
        rf"(?P<count>{COUNT_TOKEN})\s+(?P<room>{ROOM_TOKEN})\s+"
        rf"(?:in|on|at|to|for)\s+(?:the\s+)?(?P<floor>{FLOOR_TOKEN})\b",
        re.IGNORECASE,
    )
    reverse = re.compile(
        rf"(?P<floor>{FLOOR_TOKEN})\s+(?:has|have|with|to|=|:)\s*"
        rf"(?P<count>{COUNT_TOKEN})\s+(?P<room>{ROOM_TOKEN})\b",
        re.IGNORECASE,
    )
    inherited = re.compile(
        rf"(?P<count>{COUNT_TOKEN})\s+(?:of\s+them\s+)?"
        rf"(?:in|on|at|to|for)\s+(?:the\s+)?(?P<floor>{FLOOR_TOKEN})\b",
        re.IGNORECASE,
    )

    for clause in clauses:
        match = direct.search(clause) or reverse.search(clause)
        room_type = _room_type(match.group("room")) if match else None
        if match and room_type:
            inherited_room = room_type
        elif inherited_room:
            match = inherited.search(clause)
            room_type = inherited_room if match else None
        if not match or not room_type:
            continue
        level = floor_level(match.group("floor"))
        if level is None:
            continue
        result.setdefault(level, {})[room_type] = _count(match.group("count"))

    for level, counts in _section_room_counts(raw_text).items():
        result.setdefault(level, {}).update(counts)

    return result


def aggregate_floor_room_counts(program: Dict[int, Dict[str, int]]) -> Dict[str, int]:
    """Collapse a per-floor program into whole-building room totals."""
    totals: Dict[str, int] = {}
    for counts in program.values():
        for room_type, count in counts.items():
            totals[room_type] = totals.get(room_type, 0) + int(count)
    return totals
