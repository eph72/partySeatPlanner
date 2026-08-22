# Party Seat Planner

A clean visual desktop planner for four horizontal banquet tables, with 24 seats
per table (12 along each side). It uses Python's built-in Tkinter plus a small
offline first-name database for broader gender inference.

The room has 96 seats in total. If the guest file contains more than 96 people,
the extras start on the Bench and can be swapped into seats as needed.

## Start it

```bash
python3 -m pip install -r requirements.txt
python3 party_seat_planner.py
```

The included `guests.txt` contains 100 sample people. Replace it with your real
list (one full name per line) and start the app again. Names are inferred with UK
weighting and never sent online. For an ambiguous name, add `| M` or `| F`:

```text
Alex Morgan | F
Sam Taylor | M
```

A different text file can
also be selected at launch:

```bash
python3 party_seat_planner.py --guests my_party.txt
```

## Controls

- Drag a guest from one seat to another. Occupied seats swap guests.
- Drag a guest to the grey Bench, or double-click their seat to clear it.
- Drag a guest from the Bench back onto any unlocked seat.
- Right-click a seat to lock/unlock it. Locked seats have an orange outline.
- Drag any of the four long tables by its white centre to arrange the room.
- Pinch with two fingers on a Mac trackpad to zoom around the pointer. Two-finger
  scrolling pans a zoomed view; `Command+0` resets it. `Command+scroll` is also
  available as a zoom fallback.
- Double-click the centre/name of a table to rename it. Custom table names are
  included in saved plans.
- **Shuffle seats** preserves all locked seats.
- **Alternate M / F** uses first-name inference and preserves locked seats. If
  the numbers or locked positions make a perfect pattern impossible, the app
  reports how many exceptions were needed.
- **Edit guests** marks absentees and lets you correct any inferred M/F value;
  absentees appear in the grey Not Attending box.
- Saved plans are readable JSON files in the automatically created `saves`
  folder. Click a saved plan to load, rename, or delete it.

## Generate another test list

```bash
python3 generate_test_guests.py --count 100 --seed 2026
```

This replaces `guests.txt`. To write elsewhere, add `--output another.txt`.

## Run the automated checks

```bash
python3 -m unittest -v
python3 party_seat_planner.py --smoke-test
```

The smoke test builds the small native macOS pinch helper, sends a synthetic
magnification through the same pipe used by the trackpad, verifies that zoom
changes, and exits. If native support is unavailable, the app remains usable
with `Command+scroll` or `Command+plus/minus`.
