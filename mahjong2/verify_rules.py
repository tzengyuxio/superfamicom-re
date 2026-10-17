#!/usr/bin/env python3
"""Check the rule tables (rom.Rom.parlor_rules: standard set $01:D382, parlor overrides $01:D398 / $01:D39F,
dependencies $01:D3F1) against the game, in Mesen.

At the start of a table game, $01:8F8A loads the player's rule set (a new save holds the standard set) into $0E02
(one byte per item), replaces it with the standard set in parlor 1 or applies the parlor's (item, value) pairs
otherwise, then clears the items whose condition item is 0. A savestate before that (tools/sequences.py RULES_SAVE)
is replayed once per parlor 0-6 (the hook at $01:8F8E sets $1A01, the current parlor), first with the standard set,
then with a player rule set (WRAM $192F) of every item at its last value, so that every override shows; the 44 bytes
at $0E02 must equal rom.parlor_rules(k, rule set). The unmodified run is parlor 0 (あなたのいえ). Every value must
also be below the item's number of values ($01:D356), except 持ち点 16,000 (value 7) of parlor 3, which only an
override can set.

Usage: .venv/bin/python mahjong2/verify_rules.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import sequences as sq
from replay import presses, replay
from rom import DEFAULT_ROM, PARLOR_COUNT, RULE_ITEMS, Rom


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證規則表（Mesen）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    pre = next(p for p in presses(sq.TO_GAME, 10) if p[0] > sq.RULES_SAVE)[0] - sq.RULES_SAVE
    reads = [("wram", sq.RULES, RULE_ITEMS), ("wram", sq.PARLOR, 1)]
    items = rom.rule_items()
    alt = [it["count"] - 1 for it in items]   # a player rule set with every item at its last value
    alt_raw = bytes(alt[2 * i] << 4 | alt[2 * i + 1] for i in range(RULE_ITEMS // 2))
    runs, what = [{"steps": f"w{pre} a:10", "shot": pre + 150, "read": reads}], [(None, None)]
    for rule_set in (None, alt):
        for k in range(PARLOR_COUNT):
            wram = [(sq.PARAM & 0xFFFF, bytes([0] * 6 + [1, k]))]
            if rule_set:
                wram.append((sq.RULE_SETS, alt_raw))
            runs.append({"steps": f"w{pre} a:10", "shot": pre + 150, "read": reads, "wram": wram})
            what.append((k, rule_set))
    res = replay(rom.path, sq.TO_GAME, sq.RULES_SAVE, runs, extra_lua=sq.HOOK_LUA, timeout=600)
    errors = 0
    for (k, rule_set), (rules, parlor) in zip(what, res):
        want = rom.parlor_rules(0 if k is None else k, rule_set)
        ok = list(rules) == want and parlor[0] == (0 if k is None else k)
        diff = [f"{items[i]['name']} {rules[i]}≠{want[i]}" for i in range(RULE_ITEMS) if rules[i] != want[i]]
        changed = [f"{items[i]['name']}={items[i]['labels'][v] if v < items[i]['count'] else rom.starting_points(v)}"
                   for i, v in enumerate(want) if v != items[i]["standard"]]
        name = ("natural" if k is None else f"parlor {k}") + (" (all last values)" if rule_set else "")
        print(f"[{name}] $1A01={parlor[0]}: " + ("OK" if ok else f"NG {diff}")
              + (f"  (vs standard: {', '.join(changed)})" if changed and not rule_set else ""))
        errors += not ok
    bad_range = [(k, i) for k in range(PARLOR_COUNT) for i, v in enumerate(rom.parlor_rules(k))
                 if v >= items[i]["count"] and not (k == 3 and i == 10 and v == 7)]
    print(f"[ranges] values within $01:D356: {'OK' if not bad_range else f'NG {bad_range}'}")
    errors += len(bad_range)
    print(("ALL OK" if not errors else f"{errors} problem(s)") + f" ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
