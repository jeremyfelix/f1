#!/usr/bin/env python3
"""Verify the chart pages agree with each other and with the ledger.

Run after applying races, or after any hand edit. Exits non-zero on a failure,
so it works as a pre-commit or CI gate.

    python3 tools/check.py
"""
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import pages  # noqa: E402

problems = []
notes = []


def fail(msg):
    problems.append(msg)


def note(msg):
    notes.append(msg)


def check_ledger(races):
    dates = [r["date"] for r in races]
    if dates != sorted(dates):
        fail("data/races.json: races are not in date order")
    dupes = {d for d in dates if dates.count(d) > 1}
    if dupes:
        fail("data/races.json: more than one race on %s" % ", ".join(sorted(dupes)))
    for race in races:
        if race.get("team") and race["team"] not in pages.TEAMS:
            fail("%s: unknown team %r" % (race["date"], race["team"]))
        if race.get("team") and not race.get("winner"):
            fail("%s: names a winning team but no winner" % race["date"])


def check_watermarks(races):
    marks = {p: pages.watermark(pages.read(p)) for p in pages.PAGES}
    if len(set(marks.values())) > 1:
        fail("pages disagree on which race they reflect: %s\n     "
             "run tools/apply-race.py to bring them level"
             % ", ".join("%s=%s" % kv for kv in sorted(marks.items())))
    if races and max(marks.values()) < races[-1]["date"]:
        fail("ledger has races newer than the pages (%s) — run tools/apply-race.py"
             % races[-1]["date"])


def check_team(team, cfg):
    label = cfg["label"]
    winners = pages.read(cfg["winners"])
    roster = pages.read(cfg["roster"])

    wins = {n: int(f[0]) for n, f in pages.rows(winners)}
    credits = sum(wins.values())
    shared = pages.const(winners, "SHARED_WINS")
    total = credits - shared

    # The winners board is the authority on wins; the roster repeats them.
    roster_rows = {n: f for n, f in pages.rows(roster)}
    for name, count in wins.items():
        if name not in roster_rows:
            note("%s: %s won for the team but has no roster row" % (label, name))
        elif int(roster_rows[name][1]) != count:
            fail("%s: %s has %d wins on the winners board but %s on the roster"
                 % (label, name, count, roster_rows[name][1]))
    for name, fields in roster_rows.items():
        if int(fields[1]) and name not in wins:
            fail("%s: %s shows %s wins on the roster but is not on the winners board"
                 % (label, name, fields[1]))
        if int(fields[1]) > int(fields[0]):
            fail("%s: %s has more wins than starts" % (label, name))

    # A current driver's tenure has to reach the last season raced.
    last_season = pages.const(roster, "LAST_SEASON")
    for name, fields in roster_rows.items():
        label_years = fields[3].strip('"')
        m = re.match(r"^(\d{4})–present$", label_years)
        if m:
            expected = last_season - int(m.group(1)) + 1
            if int(fields[2]) != expected:
                fail("%s: %s is listed %s but shows %s seasons, not %d"
                     % (label, name, label_years, fields[2], expected))

    if pages.const(winners, "LAST_SEASON") != last_season:
        fail("%s: the two pages disagree on the last season raced (%d vs %d)"
             % (label, pages.const(winners, "LAST_SEASON"), last_season))
    if pages.const(winners, "LAST_WIN_YEAR") > last_season:
        fail("%s: LAST_WIN_YEAR is after the last season raced" % label)

    # The index repeats the win total and, for McLaren, the number of winners.
    index = pages.read(pages.INDEX)
    shown = pages.marker_text(index, "wins:" + team)
    if shown != str(total):
        fail("%s: index says %s wins, the winners board totals %d"
             % (label, shown, total))
    return total, len(wins)


def check_index_prose(counts):
    index = pages.read(pages.INDEX)
    for team, (_, drivers) in counts.items():
        card = re.search(r'<a class="card" href="%s">.*?</a>'
                         % re.escape(pages.TEAMS[team]["winners"]), index, re.S)
        if not card:
            continue
        m = re.search(r"The ([a-z-]+) who won", card.group(0))
        if m and m.group(1) != pages.spell(drivers):
            fail("%s: the index card says 'The %s who won' but the board lists %d"
                 % (pages.TEAMS[team]["label"], m.group(1), drivers))


def main():
    races = pages.ledger()
    check_ledger(races)
    check_watermarks(races)
    counts = {team: check_team(team, cfg) for team, cfg in pages.TEAMS.items()}
    check_index_prose(counts)

    for team, (total, drivers) in sorted(counts.items()):
        print("%-8s %d wins across %d drivers" % (pages.TEAMS[team]["label"], total, drivers))
    for msg in notes:
        print("note: %s" % msg)
    if problems:
        print("\n%d problem(s):" % len(problems))
        for msg in problems:
            print("  - %s" % msg)
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
