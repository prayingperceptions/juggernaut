#!/usr/bin/env python3
"""Juggernaut pre-flight checks. Run before any live mission.

Usage: python3 doctor.py [--state-dir state] [--mission missions/sats_or_death.json]
"""
import argparse
import json
import os
import sys

FAIL = []


def check(name, ok, hint=""):
    print(f"[{'OK' if ok else 'FAIL'}] {name}" + (f" -- {hint}" if hint and not ok else ""))
    if not ok:
        FAIL.append(name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-dir", default="state")
    ap.add_argument("--mission", default="missions/sats_or_death.json")
    args = ap.parse_args()

    check("python >= 3.11", sys.version_info >= (3, 11), f"found {sys.version.split()[0]}")

    try:
        import juggernaut  # noqa
        check("juggernaut package importable", True)
    except ImportError as e:
        check("juggernaut package importable", False, f"{e} -- pip install -e .")

    try:
        import laya_mlx  # noqa
        check("laya-mlx brain available", True)
    except ImportError:
        check("laya-mlx brain available", False,
              "pip install laya-mlx (Apple Silicon only) -- dry-run uses FakeBrain")

    ok, hint = True, ""
    if os.path.exists(args.mission):
        try:
            m = json.load(open(args.mission))
            for f in ("name", "objective", "done_proposition", "progress_rubric"):
                if f not in m:
                    ok, hint = False, f"mission missing field: {f}"
        except json.JSONDecodeError as e:
            ok, hint = False, f"invalid JSON: {e}"
    else:
        ok, hint = False, "mission file not found"
    check(f"mission valid ({args.mission})", ok, hint)

    hp = os.path.join(args.state_dir, "hustle.json")
    if os.path.exists(hp):
        h = json.load(open(hp))
        check("payout address set", bool(h.get("payout_address", "").strip()),
              "set payout_address in " + hp)
    else:
        check("hustle.json exists", False, "created on first run -- review before live")

    print()
    if FAIL:
        print(f"doctor: {len(FAIL)} check(s) failing -- fix before a live run.")
        sys.exit(1)
    print("doctor: all checks pass. It hungers.")


if __name__ == "__main__":
    main()
