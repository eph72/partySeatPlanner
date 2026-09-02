# Party Seat Planner

A visual desktop seating planner for parties and wedding receptions. It starts
with four horizontal banquet tables with 24 seats each, giving 96 seats in
total. Extra guests wait on the Bench until a seat becomes available.

## Features

- Drag guests between seats; occupied seats swap automatically.
- Lock a seat with right-click so shuffling cannot change it.
- Shuffle every unlocked guest or create an alternating M/F arrangement.
- Shade the whole seat by its inferred M/F seating category.
- Clear guests to a Bench and drag them back when ready.
- Mark guests as not attending in an alphabetical guest editor.
- Correct an inferred M/F value in the editor or directly in the guest file.
- Add guests and rename existing guests from the editor.
- Drag, rename and arrange all four tables.
- Change each table to rectangular or round and adjust its number of seats.
- Add one chair at each end of any rectangular table.
- Pinch to zoom on supported Mac trackpads, with keyboard and scroll fallbacks.
- Save, load, rename and delete seating plans from inside the app.
- Reopen the most recently saved plan automatically at startup.
- Export a monochrome seating plan and alphabetical guest directory as PDFs.
- Open a complete in-app guide from the **Help** button.

## Requirements

- Python 3.9 or newer.
- Tk 8.6 or newer.
- Git, if cloning or updating the project from GitHub.
- macOS, Windows or Linux. Native trackpad pinch support is macOS-only.

Python 3.13 is the recommended and tested version. On macOS, do not use
Apple's `/usr/bin/python3`: it can contain Tk 8.5, which may crash while opening
the first window.

## Install on macOS

### 1. Install Git

Open Terminal and install Apple's Command Line Tools:

```bash
xcode-select --install
```

If the tools are already installed, macOS will say so. Confirm Git is available:

```bash
git --version
```

Homebrew users can install Git with `brew install git` instead. See the
[official Git installation choices for macOS](https://git-scm.com/install/mac).

### 2. Install a current Python

Download and run a Python 3.13 universal installer from the
[official Python macOS downloads page](https://www.python.org/downloads/macos/),
then close and reopen Terminal.

Check that Python and Tk are the correct versions:

```bash
python3.13 --version
python3.13 -c "import tkinter; print('Tk', tkinter.TkVersion)"
```

The second command must report Tk 8.6 or newer.

### 3. Clone and install the app

```bash
cd ~/Documents
git clone https://github.com/eph72/partySeatPlanner.git
cd partySeatPlanner
python3.13 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

### 4. Start the app

```bash
./.venv/bin/python party_seat_planner.py
```

For later launches, open Terminal, return to the project folder and run the same
start command. The virtual environment only needs to be created once.

### Double-click launch on macOS

After cloning, you can instead double-click `run_party_seat_planner.command` in
Finder. On its first launch it finds a compatible Python, creates `.venv`,
installs the offline name database and PDF exporter, then starts the app. Later
launches start the app immediately. The launcher minimises its own Terminal
window while the planner is open and closes that window when the planner exits.
If startup fails, the Terminal window is restored so you can read the error.

If macOS asks for confirmation the first time, right-click the file, choose
**Open**, then confirm **Open**.

## Install on Windows

1. Install [Git for Windows](https://git-scm.com/install/windows).
2. Install Python 3.13 from the
   [official Python Windows downloads page](https://www.python.org/downloads/windows/).
3. Open PowerShell and run:

```powershell
cd $HOME\Documents
git clone https://github.com/eph72/partySeatPlanner.git
cd partySeatPlanner
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe party_seat_planner.py
```

Using the virtual environment's Python directly avoids PowerShell activation-policy
issues.

## Install on Debian or Ubuntu Linux

Install Git, Python, Tk and virtual-environment support:

```bash
sudo apt update
sudo apt install git python3 python3-pip python3-tk python3-venv
```

Then clone and start the app:

```bash
cd ~/Documents
git clone https://github.com/eph72/partySeatPlanner.git
cd partySeatPlanner
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python party_seat_planner.py
```

Other distributions can use the appropriate command from the
[official Git Linux installation page](https://git-scm.com/install/linux).

## Using your guest list

Edit `guests.txt` and enter one full name per line:

```text
Alice Hodges
Jude Rothwell
Lydia Brassil
```

Blank lines and lines beginning with `#` are ignored. You can also keep another
file and select it when launching:

```bash
./.venv/bin/python party_seat_planner.py --guests my_party.txt
```

The app infers an M/F seating category from each first name using an offline name
database with UK weighting. Nothing is uploaded. Name-based inference cannot be
perfect, so ambiguous names can be set explicitly:

```text
Alex Morgan | F
Sam Taylor | M
```

You can also change M/F beside a person in **Edit guests**. Editor corrections
are retained in saved seating plans; add `| M` or `| F` to the text file if the
correction should also apply whenever a completely new plan is started.

The first 96 guests are initially seated. Any additional guests start on the
Bench and can be swapped into the plan by dragging.

## Controls

| Action | Control |
| --- | --- |
| Move or swap a guest | Drag one name onto another unlocked seat |
| Move a guest to the Bench | Double-click the seat, or drag it to the Bench |
| Reseat a benched guest | Drag their name from the Bench onto a seat |
| Lock or unlock a seat | Right-click the seat |
| Move a table | Drag its white centre |
| Rename a table | Double-click its centre or name |
| Shuffle unlocked guests | Click **Shuffle seats** |
| Alternate M/F seating | Click **Alternate M / F** |
| Change attendance or M/F | Click **Edit guests** |
| Change everyone at once | Click **Check all** or **Uncheck all** in **Edit guests** |
| Add or rename a guest | Use **Add guest** or **Rename** in **Edit guests** |
| Change table shape or capacity | Click **Edit layout** |
| Export both PDFs | Click **Export PDFs**, name the export and choose a folder |
| Open the complete controls guide | Click **Help** |
| Zoom on a Mac trackpad | Pinch with two fingers |
| Zoom fallback on macOS | Command+scroll or Command+plus/minus |
| Reset the view on macOS | Command+0 |
| Pan a zoomed view | Two-finger scroll; hold Shift for horizontal movement |

Locked seats have an orange outline and padlock. Shuffle operations never move,
clear or replace a locked guest. If the guest balance or locked positions make a
perfect alternating pattern impossible, the status bar reports the number of
exceptions.

## Saved plans

Click **+ Save** in the sidebar and name the plan. Saves are readable JSON files
inside the automatically created `saves` folder. Each saved-plan button provides
options to load, rename or delete it. When the app starts, it automatically
opens the most recent readable save; if that file is damaged, it safely tries
the next newest save.

A save includes:

- guest attendance and corrected M/F values;
- seat assignments and locks;
- table positions, custom table names, shapes, capacities and end chairs.

## Custom table layouts

Click **Edit layout** to choose **Rectangular** or **Round** for each table and
set between 2 and 30 side/round seats. For a rectangular table, **End chairs**
adds one extra chair at each end. Reducing capacity keeps the earliest seats and
moves any displaced guests to the Bench after asking for confirmation.

## PDF exports

Click **Export PDFs** in the sidebar, enter a name and choose a destination
folder. The app creates two files without overwriting earlier exports:

- an A3 landscape seating plan with one large page for each table in its selected
  rectangular or round shape;
- an A4 guest list headed **Guest list**, with one column per table and each
  table's seated guests sorted alphabetically by surname.

The seating-plan PDF is monochrome and deliberately omits all seat colours and
lock indicators, making it suitable for printing or sharing with a venue.
The guest-list export has no footer, page count or extra summary text. Guests on
the Bench or marked not attending are omitted from both exports.

## Updating an existing installation

From inside the project folder:

```bash
git pull
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python party_seat_planner.py
```

On Windows, replace `./.venv/bin/python` with
`.\.venv\Scripts\python.exe`.

## Troubleshooting

### `Segmentation fault` or Tk 8.5 on macOS

Check the Tk version used by the selected Python:

```bash
python3 -c "import tkinter; print('Tk', tkinter.TkVersion)"
```

If it reports 8.5, install Python 3.13 from python.org and use `python3.13` to
create the virtual environment as shown above. The app now detects Tk 8.5 before
window creation and exits with a readable message instead of allowing the known
crash path.

### Pinch zoom causes a machine-specific problem

Disable only the native gesture bridge. Keyboard and Command+scroll zoom remain:

```bash
./.venv/bin/python party_seat_planner.py --no-native-pinch
```

### `No module named gender_guesser`

Install the requirements using the same Python that starts the app:

```bash
./.venv/bin/python -m pip install -r requirements.txt
```

### The wrong guest file opens

Specify the file explicitly:

```bash
./.venv/bin/python party_seat_planner.py --guests /path/to/guests.txt
```

## Generate test guests

The repository includes a 100-person sample list. To replace it with another
repeatable test list:

```bash
./.venv/bin/python generate_test_guests.py --count 100 --seed 2026
```

To preserve `guests.txt`, choose another output file:

```bash
./.venv/bin/python generate_test_guests.py --count 100 --output test_guests.txt
```

## Run the automated checks

```bash
./.venv/bin/python -m unittest -v
./.venv/bin/python party_seat_planner.py --smoke-test
```

The unit suite checks seating, locking, shuffling, name inference, saves, table
names, zoom calculations and legacy-Python compatibility. On macOS, the smoke
test also builds the small native pinch helper, sends a synthetic magnification
event through it and verifies that zoom changes.
