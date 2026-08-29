# Updating the pages after a race

```
$EDITOR data/races.json        # append the race
python3 tools/apply-race.py    # fold it into the pages
python3 tools/check.py         # verify
```

`apply-race.py` is safe to re-run — every page carries a watermark comment naming
the last race it reflects, and only entries dated after it are applied.
`--dry-run` reports what would change without writing.

## What the tooling owns

| Maintained automatically | Still written by hand |
| --- | --- |
| Race starts and win tallies in the data arrays | The standfirst for a milestone win (`"prose": "manual"`) |
| The nationality tables on the six pages that fly flags | A new driver's nationality, in `data/drivers.json` |
| Board order (the pages sort themselves) | The championship-history pages, once a season |
| Hero stat figures (derived in-page from the arrays) | New roster rows for a debuting driver |
| `WIN_YEARS`, `LAST_WIN_YEAR`, `LAST_SEASON` | `f1-lineage.html` |
| Win counts and closing clause on `index.html` | |
| Season spans in the headings of the four race pages | |

The hero figures are no longer stored anywhere: each page computes them from its
own table at render time, so a bumped tally cannot disagree with the number
printed above it. Only figures a table genuinely cannot supply are constants, and
they sit together at the top of each page's script.

## Adding a driver

A race result carries no debut year or tenure, so `apply-race.py` stops rather
than inventing a roster row:

```
2027-03-07: Andrea Kimi Antonelli is not on the mclaren roster page.
```

Add the row to the roster page's `data` array first, with the driver's starts at
zero and their years label ending in `–present`, then re-run. A first-time *winner*
needs no such step — they are inserted onto the winners board automatically, and
the index's "The twenty-two who won" is respelled to match.

Their nationality is the other thing a race result never carries. Add them to
`data/drivers.json` at the same time and `apply-race.py` gives them a flag as it
goes; leave it out and it says so, the driver is listed without one, and
`check.py` keeps reporting it until you fill it in.

## Nationality flags

```
$EDITOR data/drivers.json      # name -> ISO 3166-1 alpha-2 code
python3 tools/apply-flags.py   # write the inline tables
python3 tools/check.py         # verify
```

The pages fetch nothing, so each carries its own inline copy of the rows it
needs — only the drivers it lists, only the countries they raced for.
`apply-flags.py` regenerates all six copies from `data/drivers.json`, and is
idempotent and `--dry-run`-able. The flag glyph itself is never stored: the
pages derive the emoji from the code's two letters, so a code is the only thing
that can fall out of step. Six pages carry a table: the two winners boards, the
two rosters, and the drivers' champions list on each championship-history page.

Windows ships no flag glyphs and draws the two letters instead, which still
reads as a nationality; the flag cell is fixed-width so the names line up either
way.

## What `check.py` enforces

- Every page reflects the same race, and the ledger has nothing newer.
- Win tallies agree between each team's winners board and its roster page.
- Nobody has more wins than starts, or wins without a place on the board.
- A driver listed `2019–present` has a season count reaching the last season raced.
- The index's win totals and spelled-out winner counts match the boards.
- Every driver a page lists carries a flag, no page carries a flag for a driver
  it does not list, and all six agree with `data/drivers.json`.

It exits non-zero on failure, so it works as a pre-commit hook or CI step.

These it reports as notes rather than failures, because resolving them needs a
source rather than arithmetic:

- **Winners with no roster row.** Maurice Trintignant won the 1955 Monaco GP for
  Ferrari but is absent from the Ferrari roster page, which suggests the roster's
  1950s coverage has other gaps.
- **Drivers with no nationality on file.** The page lists them without a flag
  rather than guessing one.

## Ferrari's 251st credit

The Ferrari winners board holds 251 driver credits for 250 team victories: Luigi
Musso started the 1956 Argentine GP and Juan Manuel Fangio finished it, and both
hold the win. That is what `SHARED_WINS` on the page accounts for. If a future
shared win ever happens, increment it.
