"""Automated checks for the model, persistence and test-data generator."""

from __future__ import annotations

import json
from pathlib import Path
import random
import tempfile
import unittest

from generate_test_guests import generate_names
from party_seat_planner import offset_after_zoom, runtime_compatibility_issue
from seat_planner_model import (
    Guest,
    SaveManager,
    Seat,
    SeatingPlan,
    gender_database_available,
    infer_gender,
    parse_guest_entry,
    read_guest_names,
)


class PythonCompatibilityTests(unittest.TestCase):
    def test_dataclasses_do_not_require_python_310_slots(self) -> None:
        self.assertNotIn("__slots__", Guest.__dict__)
        self.assertNotIn("__slots__", Seat.__dict__)

    def test_old_macos_tk_is_rejected_before_window_creation(self) -> None:
        issue = runtime_compatibility_issue(system="Darwin", tk_version=8.5)
        self.assertIn("can crash", issue)
        self.assertIsNone(runtime_compatibility_issue(system="Darwin", tk_version=8.6))
        self.assertIsNone(runtime_compatibility_issue(system="Linux", tk_version=8.5))


class GenderInferenceTests(unittest.TestCase):
    def test_known_names(self) -> None:
        self.assertEqual(infer_gender("Charlotte Baker"), "F")
        self.assertEqual(infer_gender("Oliver Cooper"), "M")

    def test_broad_offline_database_handles_custom_names(self) -> None:
        self.assertTrue(gender_database_available())
        self.assertEqual(infer_gender("Siobhan O'Brien"), "F")
        self.assertEqual(infer_gender("Muhammad Khan"), "M")
        self.assertEqual(infer_gender("Nathaniel Price"), "M")
        self.assertEqual(infer_gender("Gertrude Evans"), "F")
        self.assertEqual(infer_gender("Chloë Martin"), "F")

    def test_titles_and_explicit_overrides(self) -> None:
        self.assertEqual(infer_gender("Dr Charlotte Baker"), "F")
        self.assertEqual(parse_guest_entry(" Alex Morgan | f "), ("Alex Morgan", "F"))
        self.assertEqual(parse_guest_entry("Sam Taylor"), ("Sam Taylor", None))
        with self.assertRaisesRegex(ValueError, "use 'Full Name"):
            parse_guest_entry("Alex Morgan | X")

    def test_sample_generator_is_balanced_and_unique(self) -> None:
        names = generate_names(100, seed=42)
        self.assertEqual(len(names), 100)
        self.assertEqual(len(set(names)), 100)
        genders = [infer_gender(name) for name in names]
        self.assertEqual(genders.count("M"), 50)
        self.assertEqual(genders.count("F"), 50)


class SeatingPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.names = generate_names(100, seed=5)
        self.plan = SeatingPlan.from_names(self.names)

    def test_builds_four_tables_of_twenty_four_for_one_hundred_guests(self) -> None:
        self.assertEqual(self.plan.table_count, 4)
        self.assertEqual(len(self.plan.seats), 96)
        self.assertEqual(len(self.plan.attending_guest_ids()), 100)
        self.assertEqual(len(self.plan.bench_guest_ids()), 4)

    def test_duplicate_display_names_remain_distinct_guests(self) -> None:
        plan = SeatingPlan.from_names(["Sam Taylor", "Sam Taylor"])
        self.assertEqual(len(plan.guests), 2)
        self.assertNotEqual(*plan.guests.keys())

    def test_guest_file_gender_override_and_editor_change(self) -> None:
        plan = SeatingPlan.from_names(["Alex Morgan | F", "Sam Taylor | M"])
        guests = list(plan.guests.values())
        self.assertEqual([(guest.name, guest.gender) for guest in guests], [
            ("Alex Morgan", "F"),
            ("Sam Taylor", "M"),
        ])
        plan.set_gender(guests[0].id, "M")
        self.assertEqual(guests[0].gender, "M")

    def test_clear_move_swap_and_bench(self) -> None:
        first = self.plan.seats[0].guest_id
        second = self.plan.seats[1].guest_id
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(self.plan.clear_seat(0), first)
        self.assertIn(first, self.plan.bench_guest_ids())
        self.assertTrue(self.plan.move_guest(first, 1))
        self.assertEqual(self.plan.seats[1].guest_id, first)
        self.assertIn(second, self.plan.bench_guest_ids())

    def test_lock_prevents_changes_and_survives_randomisation(self) -> None:
        locked_guest = self.plan.seats[7].guest_id
        self.plan.toggle_lock(7)
        self.assertIsNone(self.plan.clear_seat(7))
        self.assertFalse(self.plan.move_guest(locked_guest, 8))
        self.plan.randomize(rng=random.Random(10))
        self.assertEqual(self.plan.seats[7].guest_id, locked_guest)
        self.assertTrue(self.plan.seats[7].locked)

    def test_balanced_gender_randomisation_alternates_every_table(self) -> None:
        message = self.plan.randomize(gender_alternating=True, rng=random.Random(9))
        self.assertIn("Alternating", message)
        for table in range(self.plan.table_count):
            seats = [seat for seat in self.plan.seats if seat.table == table]
            genders = [self.plan.guests[seat.guest_id].gender for seat in seats]
            for previous, current in zip(genders, genders[1:] + genders[:1]):
                self.assertNotEqual(previous, current)

    def test_not_attending_guest_is_unseated(self) -> None:
        guest_id = self.plan.seats[3].guest_id
        self.plan.toggle_lock(3)
        self.plan.set_attending(guest_id, False)
        self.assertIsNone(self.plan.seats[3].guest_id)
        self.assertFalse(self.plan.seats[3].locked)
        self.assertIn(guest_id, self.plan.absent_guest_ids())

    def test_table_can_be_renamed(self) -> None:
        self.assertEqual(self.plan.table_name(1), "Table 2")
        self.assertEqual(self.plan.rename_table(1, "  Family   & Friends  "), "Family & Friends")
        self.assertEqual(self.plan.table_name(1), "Family & Friends")


class ZoomMathTests(unittest.TestCase):
    def test_focal_point_stays_fixed_when_zooming(self) -> None:
        # A point at x=700 maps to base x=700 before zoom.  The new offset
        # should keep it at x=700 after zooming from 1x to 2x around itself.
        offset = offset_after_zoom(0, 1, 2, 700, 500)
        remapped = 500 + (700 - 500) * 2 + offset
        self.assertAlmostEqual(remapped, 700)


class SaveTests(unittest.TestCase):
    def test_round_trip_rename_and_delete(self) -> None:
        plan = SeatingPlan.from_names(generate_names(20, seed=11))
        plan.toggle_lock(2)
        plan.clear_seat(5)
        plan.table_positions[0] = (0.2, 0.4)
        plan.rename_table(0, "Top Table")
        with tempfile.TemporaryDirectory() as folder:
            manager = SaveManager(Path(folder) / "saves")
            path = manager.save(plan, "Saturday / final")
            self.assertEqual(path.name, "Saturday final.json")
            loaded = manager.load(path)
            self.assertEqual(loaded.to_dict()["guests"], plan.to_dict()["guests"])
            self.assertEqual(loaded.seats[2].locked, True)
            self.assertEqual(loaded.table_positions[0], (0.2, 0.4))
            self.assertEqual(loaded.table_name(0), "Top Table")
            renamed = manager.rename(path, "Really final")
            self.assertTrue(renamed.exists())
            manager.delete(renamed)
            self.assertEqual(manager.list_saves(), [])

    def test_invalid_format_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            manager = SaveManager(Path(folder))
            bad = Path(folder) / "bad.json"
            bad.write_text(json.dumps({"format_version": 99}), encoding="utf-8")
            with self.assertRaises(ValueError):
                manager.load(bad)

    def test_bundled_guest_file_is_readable(self) -> None:
        names = read_guest_names(Path(__file__).resolve().parent / "guests.txt")
        self.assertEqual(len(names), 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
