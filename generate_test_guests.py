#!/usr/bin/env python3
"""Generate a realistic, balanced guest list for trying the first build."""

from __future__ import annotations

import argparse
from pathlib import Path
import random


FEMALE_NAMES = [
    "Abigail", "Alice", "Amelia", "Amy", "Anna", "Bethany", "Caroline", "Charlotte",
    "Chloe", "Claire", "Daisy", "Eleanor", "Ella", "Ellie", "Emily", "Emma", "Erin",
    "Evelyn", "Fiona", "Florence", "Francesca", "Gemma", "Georgia", "Grace", "Hannah",
    "Harriet", "Hazel", "Holly", "Imogen", "Isabella", "Isla", "Jasmine", "Jessica",
    "Katie", "Laura", "Lauren", "Leah", "Lily", "Lucy", "Maya", "Megan", "Mia",
    "Molly", "Naomi", "Natalie", "Olivia", "Phoebe", "Poppy", "Rachel", "Rebecca",
    "Rose", "Rosie", "Ruby", "Samantha", "Sarah", "Scarlett", "Sophie", "Victoria",
]

MALE_NAMES = [
    "Aaron", "Adam", "Adrian", "Alexander", "Andrew", "Anthony", "Arthur", "Ben",
    "Benjamin", "Bradley", "Callum", "Cameron", "Charles", "Christopher", "Connor",
    "Daniel", "David", "Dominic", "Dylan", "Edward", "Elliot", "Ethan", "Finley",
    "Fraser", "Freddie", "George", "Harry", "Henry", "Hugh", "Isaac", "Jack", "Jacob",
    "James", "Jamie", "Joe", "John", "Jonathan", "Joseph", "Joshua", "Kieran", "Liam",
    "Louis", "Luke", "Matthew", "Max", "Michael", "Nathan", "Noah", "Oliver", "Oscar",
    "Owen", "Patrick", "Ryan", "Samuel", "Sebastian", "Thomas", "Toby", "William",
]

LAST_NAMES = [
    "Adams", "Allen", "Anderson", "Baker", "Bell", "Bennett", "Brooks", "Brown",
    "Butler", "Campbell", "Carter", "Chapman", "Clark", "Collins", "Cooper", "Davies",
    "Davis", "Edwards", "Evans", "Fisher", "Foster", "Gray", "Green", "Griffiths",
    "Hall", "Harris", "Harrison", "Hill", "Holmes", "Howard", "Hughes", "Jackson",
    "James", "Jenkins", "Johnson", "Jones", "Kelly", "King", "Knight", "Lee", "Lewis",
    "Marshall", "Martin", "Mason", "Miller", "Mitchell", "Moore", "Morgan", "Morris",
    "Murphy", "Murray", "Owen", "Palmer", "Parker", "Patel", "Phillips", "Powell",
    "Price", "Reed", "Rees", "Richards", "Roberts", "Robinson", "Rogers", "Russell",
    "Scott", "Shaw", "Smith", "Stevens", "Stewart", "Taylor", "Thomas", "Thompson",
    "Turner", "Walker", "Ward", "Watson", "Webb", "White", "Williams", "Wilson", "Wood",
    "Wright", "Young",
]


def generate_names(count: int, seed: int = 2026) -> list[str]:
    if count < 1:
        raise ValueError("count must be at least 1")
    rng = random.Random(seed)
    female_count = count // 2
    male_count = count - female_count
    used: set[str] = set()
    names: list[str] = []
    for index in range(max(female_count, male_count)):
        for first_names, wanted in ((FEMALE_NAMES, female_count), (MALE_NAMES, male_count)):
            if index >= wanted:
                continue
            attempt = 0
            while True:
                first = first_names[index % len(first_names)]
                last = rng.choice(LAST_NAMES)
                full_name = f"{first} {last}"
                if full_name not in used:
                    break
                attempt += 1
                if attempt > len(LAST_NAMES):
                    full_name = f"{first} {last} {index + 1}"
                    break
            used.add(full_name)
            names.append(full_name)
    rng.shuffle(names)
    return names


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a sample guest-list text file.")
    parser.add_argument("--count", type=int, default=100, help="Number of guests (default: 100).")
    parser.add_argument("--seed", type=int, default=2026, help="Repeatable random seed.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "guests.txt",
        help="Output text file (default: guests.txt beside this script).",
    )
    args = parser.parse_args()
    try:
        names = generate_names(args.count, args.seed)
    except ValueError as error:
        parser.error(str(error))
    args.output.write_text("\n".join(names) + "\n", encoding="utf-8")
    print(f"Created {args.output} with {len(names)} sample guests.")


if __name__ == "__main__":
    main()
