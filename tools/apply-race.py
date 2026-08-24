#!/usr/bin/env python3
"""Fold new race results from data/races.json into the chart pages.

Each page carries a watermark comment naming the last race it reflects, so this
is idempotent and resumable: every page independently picks up only the ledger
entries dated after its own watermark.

    python3 tools/apply-race.py            # apply pending races
    python3 tools/apply-race.py --dry-run  # report what would change

What it maintains: race starts and win tallies in the data arrays, the derived
constants (WIN_YEARS, LAST_WIN_YEAR, LAST_SEASON), the win counts on the index,
the season spans in the headings of the pages it owns, and the templated closing
clause of the two standfirsts. Everything else is prose, and stays hand-written.
"""
import argparse
import calendar
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import pages  # noqa: E402


def year(race):
    return int(race["date"][:4])


def started(race, team):
    return race.get("starters", {}).get(team, [])


def pending(html, races):
    mark = pages.watermark(html)
    return [r for r in races if r["date"] > mark]


def bump_own_heading(html, old, new):
    """Move the closing year of this page's own '1966–2026' heading span."""
    return re.sub(r'<p class="eyebrow">.*?</p>',
                  lambda m: m.group(0).replace("–%d" % old, "–%d" % new),
                  html, count=1, flags=re.S)


def roll_season(html, race, log, page):
    """Advance LAST_SEASON when a race is the team's first of a new year."""
    last = pages.const(html, "LAST_SEASON")
    if year(race) <= last:
        return html, False
    html = pages.set_const(html, "LAST_SEASON", year(race))
    html = bump_own_heading(html, last, year(race))
    log.append("    %s: season rolled over to %d" % (page, year(race)))
    return html, True


def apply_winners(html, team, races, log):
    """Winner tallies, the win-year constants, and the standfirst clause."""
    for race in races:
        if race.get("team") == team:
            driver = race["winner"]
            if pages.has_row(html, driver):
                html = pages.edit_row(html, driver, 0, +1)
            else:
                html = pages.add_winner_row(html, driver)
                log.append("    %s joins the winners board" % driver)
            log.append("    %s +1 win (%s)" % (driver, race["name"]))

            if year(race) > pages.const(html, "LAST_WIN_YEAR"):
                html = pages.set_const(html, "WIN_YEARS", pages.const(html, "WIN_YEARS") + 1)
                html = pages.set_const(html, "LAST_WIN_YEAR", year(race))
                log.append("    first win of %d: WIN_YEARS +1" % year(race))

            if race.get("prose") == "manual":
                log.append("    standfirst left alone (prose: manual) — reword it by hand")
            else:
                month = calendar.month_name[int(race["date"][5:7])]
                html = pages.marker(html, "latest-win", "%s's victory at %s in %s %d"
                                    % (driver, race["circuit"], month, year(race)))
        if started(race, team):
            html, _ = roll_season(html, race, log, "winners")
    return html


def apply_roster(html, team, races, log):
    """One race start per listed driver, plus a season when the year rolls over."""
    baseline = pages.const(html, "LAST_SEASON")
    credited = {}
    for race in races:
        starters = started(race, team)
        for driver in starters:
            try:
                html = pages.edit_row(html, driver, 0, +1)
            except KeyError:
                raise SystemExit(
                    "%s: %s is not on the %s roster page.\nA race result carries no "
                    "debut year or tenure, so add the row by hand first, then re-run."
                    % (race["date"], driver, team))
        if race.get("team") == team:
            html = pages.edit_row(html, race["winner"], 1, +1)
        if starters:
            log.append("    +1 start: %s" % ", ".join(starters))

        # Credit a season the first time a current driver starts in a new year,
        # which need not be their team's opener. check.py verifies the totals.
        if year(race) > baseline:
            for driver in starters:
                if year(race) in credited.setdefault(driver, set()):
                    continue
                _, fields = next(r for r in pages.rows(html) if r[0] == driver)
                if "present" in fields[3]:
                    html = pages.edit_row(html, driver, 2, +1)
                    credited[driver].add(year(race))
                    log.append("    %s +1 season (%d)" % (driver, year(race)))
        if starters:
            html, _ = roll_season(html, race, log, "roster")
    return html


def total_wins(winners_html):
    credits = sum(int(f[0]) for _, f in pages.rows(winners_html))
    return credits - pages.const(winners_html, "SHARED_WINS")


def bump_card_year(html, href, old, new):
    """Bump a year span on the index, inside one card only — the championship
    cards stop at their own last charted season and must not be dragged along."""
    return re.sub(r'<a class="card" href="%s">.*?</a>' % re.escape(href),
                  lambda m: m.group(0).replace("–%d" % old, "–%d" % new),
                  html, count=1, flags=re.S)


def set_card_count(html, href, count):
    """Keep a card's spelled-out driver count ('The twenty-two who won') honest."""
    def fix(card):
        return re.sub(r"The [a-z-]+ who won",
                      "The %s who won" % pages.spell(count), card.group(0), count=1)
    return re.sub(r'<a class="card" href="%s">.*?</a>' % re.escape(href),
                  fix, html, count=1, flags=re.S)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    races = pages.ledger()
    html = {p: pages.read(p) for p in pages.PAGES}
    log, touched, seasons = [], {}, {}

    for team, cfg in pages.TEAMS.items():
        for kind, fn in (("winners", apply_winners), ("roster", apply_roster)):
            page = cfg[kind]
            todo = pending(html[page], races)
            if not todo:
                continue
            before = pages.const(html[page], "LAST_SEASON")
            entries = len(log)
            log.append("  %s" % page)
            html[page] = fn(html[page], team, todo, log)
            if len(log) == entries + 1:      # nothing to report under this page
                log.pop()
            touched[page] = todo[-1]["date"]
            after = pages.const(html[page], "LAST_SEASON")
            if after != before:
                seasons[page] = (before, after)

    todo = pending(html[pages.INDEX], races)
    if todo:
        entries = len(log)
        log.append("  %s" % pages.INDEX)
        for team, cfg in pages.TEAMS.items():
            total = total_wins(html[cfg["winners"]])
            if pages.marker_text(html[pages.INDEX], "wins:" + team) != str(total):
                html[pages.INDEX] = pages.marker(html[pages.INDEX], "wins:" + team, str(total))
                log.append("    %s win count -> %d" % (cfg["label"], total))
            board = len(pages.rows(html[cfg["winners"]]))
            updated = set_card_count(html[pages.INDEX], cfg["winners"], board)
            if updated != html[pages.INDEX]:
                html[pages.INDEX] = updated
                log.append("    %s card -> 'The %s who won'" % (cfg["label"], pages.spell(board)))

            wins = [r for r in todo if r.get("team") == team and r.get("prose") != "manual"]
            if wins:
                race = wins[-1]
                gap = year(race) - cfg["first_win_year"]
                html[pages.INDEX] = pages.marker(
                    html[pages.INDEX], "latest:" + team, "%s at %s %s years later"
                    % (pages.surname(race["winner"]), race["circuit"], pages.spell(gap)))
                log.append("    %s blurb -> %s at %s" % (cfg["label"], pages.surname(race["winner"]),
                                                         race["circuit"]))
            for kind in ("winners", "roster"):
                if cfg[kind] in seasons:
                    old, new = seasons[cfg[kind]]
                    html[pages.INDEX] = bump_card_year(html[pages.INDEX], cfg[kind], old, new)
                    log.append("    %s card -> –%d" % (cfg[kind], new))
        if len(log) == entries + 1:
            log.pop()
        touched[pages.INDEX] = todo[-1]["date"]

    if not touched:
        print("Up to date — no races newer than the page watermarks.")
        return

    for page, date in touched.items():
        html[page] = pages.set_watermark(html[page], date)

    print("\n".join(log) if log else "  (watermarks only)")
    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return
    for page in touched:
        pages.write(page, html[page])
    print("\nUpdated %d page(s). Now run: python3 tools/check.py" % len(touched))


if __name__ == "__main__":
    main()
