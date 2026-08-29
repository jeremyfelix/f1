#!/usr/bin/env python3
"""Write the nationality tables in data/drivers.json into the chart pages.

The pages are self-contained and fetch nothing, so each carries an inline copy
of the rows it needs. This regenerates those copies from the one source, and is
idempotent — run it after adding a driver to data/drivers.json, or after adding
a driver to a page.

    python3 tools/apply-flags.py            # rewrite the inline tables
    python3 tools/apply-flags.py --dry-run  # report what would change

A page only carries the drivers it actually lists, and only the countries those
drivers come from, so a new name never grows the other five pages.
"""
import argparse
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import pages  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    source = pages.drivers_file()
    unknown = {}
    changed = []

    for page in pages.FLAG_PAGES:
        html = before = pages.read(page)
        nat, countries, missing = pages.flag_tables(page, html, source)
        if missing:
            unknown[page] = missing
        html = pages.set_flag_tables(html, nat, countries)
        if html == before:
            continue
        added = sorted(set(nat) - set(pages.nationalities(before)))
        dropped = sorted(set(pages.nationalities(before)) - set(nat))
        print("  %s: %d drivers, %d countries" % (page, len(nat), len(countries)))
        for name in added:
            print("    + %s (%s)" % (name, nat[name]))
        for name in dropped:
            print("    - %s (no longer listed on this page)" % name)
        changed.append((page, html))

    for page, missing in unknown.items():
        print("  %s: no nationality on file for %s" % (page, ", ".join(missing)))

    if not changed:
        print("Up to date — every page already matches data/drivers.json.")
    elif args.dry_run:
        print("\n--dry-run: nothing written.")
    else:
        for page, html in changed:
            pages.write(page, html)
        print("\nUpdated %d page(s). Now run: python3 tools/check.py" % len(changed))

    return 1 if unknown else 0


if __name__ == "__main__":
    sys.exit(main())
