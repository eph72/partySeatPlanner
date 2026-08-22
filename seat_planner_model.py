"""Data model and persistence for the Party Seat Planner.

The module deliberately has no Tkinter dependency.  That keeps the seating rules
easy to test and makes saved plans readable JSON files rather than opaque data.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
import math
from pathlib import Path
import random
import re
from typing import Iterable, Literal


TABLE_COUNT = 4
SEATS_PER_TABLE = 24
Gender = Literal["M", "F"]


# A broad, intentionally conservative list.  Unknown first names use a small
# spelling heuristic, so a gendered randomisation still works with ordinary UK
# party lists without adding a third-party package.
FEMALE_FIRST_NAMES = {
    "abigail", "alice", "alicia", "amanda", "amelia", "amy", "anna", "anne",
    "beth", "bethany", "beverley", "brooke", "caitlin", "caroline", "charlotte",
    "chloe", "claire", "daisy", "danielle", "deborah", "diana", "eleanor",
    "elizabeth", "ella", "ellie", "emily", "emma", "erin", "eve", "evelyn",
    "fiona", "florence", "francesca", "gabriella", "gemma", "georgia", "grace",
    "hannah", "harriet", "hazel", "heather", "helen", "holly", "imogen",
    "isabella", "isla", "jade", "jane", "jasmine", "jennifer", "jessica",
    "joanne", "julia", "karen", "katherine", "katie", "kayleigh", "kimberley",
    "laura", "lauren", "leah", "lily", "linda", "lisa", "lucy", "madeleine",
    "madison", "margaret", "maria", "mary", "maya", "megan", "melanie",
    "mia", "michelle", "molly", "naomi", "natalie", "nicola", "nicole",
    "olivia", "paige", "patricia", "phoebe", "poppy", "rachel", "rebecca",
    "rose", "rosie", "ruby", "samantha", "sarah", "scarlett", "shannon",
    "sophie", "stacey", "stephanie", "susan", "suzanne", "tanya", "tara",
    "teresa", "tracy", "vanessa", "victoria", "violet", "wendy", "zoe",
}

MALE_FIRST_NAMES = {
    "aaron", "adam", "adrian", "alexander", "andrew", "anthony", "arthur",
    "ben", "benjamin", "bradley", "brandon", "brian", "callum", "cameron",
    "charles", "chris", "christian", "christopher", "colin", "connor", "daniel",
    "darren", "david", "dean", "dominic", "douglas", "dylan", "edward",
    "elliot", "ethan", "evan", "finley", "francis", "fraser", "freddie",
    "george", "graham", "grant", "gregory", "harry", "henry", "hugh", "ian",
    "isaac", "jack", "jacob", "james", "jamie", "jason", "jay", "jeremy",
    "joe", "john", "jonathan", "jordan", "joseph", "joshua", "justin", "keith",
    "kieran", "kyle", "lawrence", "lee", "leon", "liam", "louis", "luke",
    "marcus", "mark", "martin", "matthew", "max", "michael", "nathan",
    "nicholas", "noah", "oliver", "oscar", "owen", "patrick", "paul", "peter",
    "philip", "richard", "robert", "ryan", "samuel", "scott", "sean", "sebastian",
    "simon", "stephen", "steven", "stuart", "thomas", "timothy", "toby", "tom",
    "victor", "william", "zachary",
}


def infer_gender(name: str) -> Gender:
    """Infer M/F from a conventional first name.

    The requested input has no gender column.  Exact matches are preferred; the
    fallback is deterministic so re-opening a plan never changes its result.
    """

    first = re.sub(r"[^a-z]", "", name.strip().split()[0].lower()) if name.strip() else ""
    if first in FEMALE_FIRST_NAMES:
        return "F"
    if first in MALE_FIRST_NAMES:
        return "M"
    if first.endswith(("a", "ia", "ie", "elle", "ette", "lyn", "een", "ine", "y")):
        return "F"
    return "M"


def read_guest_names(path: Path) -> list[str]:
    """Read one guest per line, keeping duplicate names as separate people."""

    names = []
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        name = " ".join(raw_line.strip().split())
        if name and not name.startswith("#"):
            names.append(name)
    if not names:
        raise ValueError(f"No guest names were found in {path.name}.")
    return names


@dataclass(slots=True)
class Guest:
    id: str
    name: str
    gender: Gender
    attending: bool = True


@dataclass(slots=True)
class Seat:
    id: int
    table: int
    position: int
    guest_id: str | None = None
    locked: bool = False


class SeatingPlan:
    """Mutable seating state with rules shared by the GUI and tests."""

    def __init__(
        self,
        guests: Iterable[Guest],
        seats: Iterable[Seat],
        table_positions: dict[int, tuple[float, float]] | None = None,
    ) -> None:
        self.guests = {guest.id: guest for guest in guests}
        self.seats = list(seats)
        self.table_positions = table_positions or {}

    @classmethod
    def from_names(
        cls,
        names: Iterable[str],
        seats_per_table: int = SEATS_PER_TABLE,
        table_count: int | None = TABLE_COUNT,
    ) -> "SeatingPlan":
        guests = [
            Guest(id=f"guest-{index:03d}", name=name, gender=infer_gender(name))
            for index, name in enumerate(names, start=1)
        ]
        table_count = table_count or max(1, math.ceil(len(guests) / seats_per_table))
        seats = [
            Seat(id=index, table=index // seats_per_table, position=index % seats_per_table)
            for index in range(table_count * seats_per_table)
        ]
        plan = cls(guests, seats)
        for seat, guest in zip(plan.seats, guests):
            seat.guest_id = guest.id
        return plan

    @property
    def table_count(self) -> int:
        return max((seat.table for seat in self.seats), default=-1) + 1

    def guest_for_seat(self, seat_id: int) -> Guest | None:
        guest_id = self.seats[seat_id].guest_id
        return self.guests.get(guest_id) if guest_id else None

    def seat_for_guest(self, guest_id: str) -> Seat | None:
        return next((seat for seat in self.seats if seat.guest_id == guest_id), None)

    def attending_guest_ids(self) -> list[str]:
        return [guest.id for guest in self.guests.values() if guest.attending]

    def bench_guest_ids(self) -> list[str]:
        seated = {seat.guest_id for seat in self.seats if seat.guest_id}
        return [
            guest.id
            for guest in self.guests.values()
            if guest.attending and guest.id not in seated
        ]

    def absent_guest_ids(self) -> list[str]:
        return [guest.id for guest in self.guests.values() if not guest.attending]

    def set_attending(self, guest_id: str, attending: bool) -> None:
        guest = self.guests[guest_id]
        guest.attending = attending
        if not attending:
            seat = self.seat_for_guest(guest_id)
            if seat:
                seat.guest_id = None
                seat.locked = False

    def toggle_lock(self, seat_id: int) -> bool:
        seat = self.seats[seat_id]
        seat.locked = not seat.locked
        return seat.locked

    def clear_seat(self, seat_id: int) -> str | None:
        seat = self.seats[seat_id]
        if seat.locked:
            return None
        guest_id = seat.guest_id
        seat.guest_id = None
        return guest_id

    def move_guest(self, guest_id: str, destination_seat_id: int) -> bool:
        """Move a guest to a seat, swapping when both guests started seated."""

        guest = self.guests.get(guest_id)
        if not guest or not guest.attending:
            return False
        destination = self.seats[destination_seat_id]
        if destination.locked:
            return False
        source = self.seat_for_guest(guest_id)
        if source and source.locked:
            return False
        displaced_id = destination.guest_id
        destination.guest_id = guest_id
        if source and source.id != destination.id:
            source.guest_id = displaced_id
        return True

    def move_guest_to_bench(self, guest_id: str) -> bool:
        source = self.seat_for_guest(guest_id)
        if not source or source.locked:
            return False
        source.guest_id = None
        return True

    def randomize(self, gender_alternating: bool = False, rng: random.Random | None = None) -> str:
        rng = rng or random.Random()
        unlocked_seats = [seat for seat in self.seats if not seat.locked]
        locked_ids = {
            seat.guest_id for seat in self.seats if seat.locked and seat.guest_id is not None
        }
        available_ids = [
            guest.id
            for guest in self.guests.values()
            if guest.attending and guest.id not in locked_ids
        ]
        rng.shuffle(available_ids)

        for seat in unlocked_seats:
            seat.guest_id = None

        if not gender_alternating:
            for seat, guest_id in zip(unlocked_seats, available_ids):
                seat.guest_id = guest_id
            return "Seats randomised. Locked seats were left unchanged."

        targets = self._best_gender_targets(unlocked_seats, available_ids, rng)
        pools: dict[Gender, list[str]] = {"M": [], "F": []}
        for guest_id in available_ids:
            pools[self.guests[guest_id].gender].append(guest_id)
        rng.shuffle(pools["M"])
        rng.shuffle(pools["F"])

        compromises = 0
        for seat in unlocked_seats:
            preferred = targets[seat.id]
            other: Gender = "F" if preferred == "M" else "M"
            if pools[preferred]:
                seat.guest_id = pools[preferred].pop()
            elif pools[other]:
                seat.guest_id = pools[other].pop()
                compromises += 1

        if compromises:
            return (
                "Gender pattern applied as closely as possible; the guest balance "
                f"required {compromises} adjacent exception{'s' if compromises != 1 else ''}."
            )
        return "Alternating M/F seating applied. Locked seats were left unchanged."

    def _best_gender_targets(
        self,
        unlocked_seats: list[Seat],
        available_ids: list[str],
        rng: random.Random,
    ) -> dict[int, Gender]:
        """Choose each table's M/F starting phase with the fewest compromises."""

        tables = sorted({seat.table for seat in self.seats})
        available_counts = {
            "M": sum(self.guests[guest_id].gender == "M" for guest_id in available_ids),
            "F": sum(self.guests[guest_id].gender == "F" for guest_id in available_ids),
        }
        candidates: list[tuple[int, tuple[Gender, ...]]] = []
        # At about 100 people this is only 2^10 combinations.
        for mask in range(1 << len(tables)):
            phases: tuple[Gender, ...] = tuple(
                "F" if mask & (1 << index) else "M" for index in range(len(tables))
            )
            target_counts = {"M": 0, "F": 0}
            locked_mismatches = 0
            for seat in self.seats:
                phase = phases[tables.index(seat.table)]
                target: Gender = phase if seat.position % 2 == 0 else ("F" if phase == "M" else "M")
                if seat.locked and seat.guest_id:
                    if self.guests[seat.guest_id].gender != target:
                        locked_mismatches += 1
                elif not seat.locked:
                    target_counts[target] += 1
            shortage = max(0, target_counts["M"] - available_counts["M"]) + max(
                0, target_counts["F"] - available_counts["F"]
            )
            candidates.append((locked_mismatches * 1000 + shortage, phases))
        best_score = min(score for score, _ in candidates)
        best_phases = rng.choice([phases for score, phases in candidates if score == best_score])
        phase_by_table = dict(zip(tables, best_phases))
        return {
            seat.id: (
                phase_by_table[seat.table]
                if seat.position % 2 == 0
                else ("F" if phase_by_table[seat.table] == "M" else "M")
            )
            for seat in unlocked_seats
        }

    def to_dict(self) -> dict:
        return {
            "format_version": 1,
            "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "guests": [asdict(guest) for guest in self.guests.values()],
            "seats": [asdict(seat) for seat in self.seats],
            "table_positions": {
                str(table): [round(position[0], 2), round(position[1], 2)]
                for table, position in self.table_positions.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SeatingPlan":
        if data.get("format_version") != 1:
            raise ValueError("This save uses an unsupported format version.")
        guests = [Guest(**item) for item in data["guests"]]
        seats = [Seat(**item) for item in data["seats"]]
        positions = {
            int(table): (float(coords[0]), float(coords[1]))
            for table, coords in data.get("table_positions", {}).items()
        }
        plan = cls(guests, seats, positions)
        valid_ids = set(plan.guests)
        seen = set()
        for seat in plan.seats:
            if seat.guest_id not in valid_ids or seat.guest_id in seen:
                seat.guest_id = None
                seat.locked = False
            elif seat.guest_id:
                seen.add(seat.guest_id)
        return plan


class SaveManager:
    """Create, list, rename and delete plan files inside one saves folder."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.folder.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def safe_name(name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9 _-]", "", name).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned[:60] or "Seating plan"

    def unique_path(self, display_name: str, exclude: Path | None = None) -> Path:
        stem = self.safe_name(display_name)
        candidate = self.folder / f"{stem}.json"
        suffix = 2
        while candidate.exists() and candidate != exclude:
            candidate = self.folder / f"{stem} {suffix}.json"
            suffix += 1
        return candidate

    def save(self, plan: SeatingPlan, display_name: str) -> Path:
        path = self.unique_path(display_name)
        path.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
        return path

    def list_saves(self) -> list[Path]:
        return sorted(self.folder.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)

    def load(self, path: Path) -> SeatingPlan:
        if path.parent.resolve() != self.folder.resolve():
            raise ValueError("Save file must be inside the saves folder.")
        return SeatingPlan.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def rename(self, path: Path, new_name: str) -> Path:
        target = self.unique_path(new_name, exclude=path)
        return path.rename(target)

    def delete(self, path: Path) -> None:
        if path.parent.resolve() != self.folder.resolve():
            raise ValueError("Save file must be inside the saves folder.")
        path.unlink()
