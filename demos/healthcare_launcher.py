#!/usr/bin/env python3
"""
TELOS Healthcare Governance Demo -- Interactive Launcher
========================================================
Interactive numbered menu for selecting and running healthcare demos.

Run:
  python3 demos/healthcare_launcher.py
  DEMO_FAST=1 python3 demos/healthcare_launcher.py
"""

import os
import sys

# Ensure the project root and demos dir are on sys.path
_DEMO_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_DEMO_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _DEMO_DIR not in sys.path:
    sys.path.insert(0, _DEMO_DIR)

from _display_toolkit import _c, _BOLD, _RESET, _DIM, W, _pause
from healthcare_scenarios import CONFIG_ORDER, CONFIG_DISPLAY


def _show_menu():
    """Display the interactive demo selection menu."""
    print()
    print(_c("  TELOS Healthcare Governance Demos", "cyan", bold=True))
    print("  {}".format(_c("\u2500" * 50, "dim")))

    for i, config_id in enumerate(CONFIG_ORDER, 1):
        display = CONFIG_DISPLAY[config_id]
        num = _c("[{}]".format(i), "cyan", bold=True)
        name = _c(display["short_name"], "white", bold=True)
        tag = _c(display["tagline"], "dim")
        print("  {} {}".format(num, name))
        print("      {}".format(tag))

    print("  {}".format(_c("\u2500" * 50, "dim")))
    print("  {} Run ALL demos sequentially".format(_c("[8]", "cyan", bold=True)))
    print("  {} Exit".format(_c("[0]", "cyan", bold=True)))
    print()


def main(output_dir=None):
    """Interactive launcher for healthcare demos."""
    from healthcare_live_demo import main as run_demo

    while True:
        _show_menu()

        try:
            raw = input("  Select demo [0-8]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue

        try:
            choice = int(raw)
        except ValueError:
            print("  {}".format(_c("Invalid selection", "red")))
            continue

        if choice == 0:
            print()
            print("  {}".format(_c("Exiting.", "dim")))
            break
        elif 1 <= choice <= 7:
            config_id = CONFIG_ORDER[choice - 1]
            display = CONFIG_DISPLAY[config_id]
            print()
            print("  {}".format(_c(
                "Launching: {}".format(display["short_name"]), "green")))
            print()
            run_demo(config_id, output_dir)
        elif choice == 8:
            print()
            print("  {}".format(_c(
                "Running all 7 healthcare demos sequentially ...", "green")))
            print()
            for config_id in CONFIG_ORDER:
                display = CONFIG_DISPLAY[config_id]
                print()
                print("  {}".format(_c(
                    "=== {} ===".format(display["short_name"]), "cyan", bold=True)))
                run_demo(config_id, output_dir)
            print()
            print("  {}".format(_c(
                "All 7 healthcare demos completed.", "green")))
        else:
            print("  {}".format(_c("Invalid selection (0-8)", "red")))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TELOS Healthcare Demo Launcher")
    parser.add_argument("--output", "-o", default=None,
                        help="Delivery folder for artifacts")
    args = parser.parse_args()
    main(args.output)
