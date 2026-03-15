#!/usr/bin/env python3
"""
TELOS OpenClaw Governance Demo -- Interactive Launcher
======================================================
Interactive numbered menu for selecting and running OpenClaw demos.

9 governance surfaces, ordered by risk tier (CRITICAL -> LOW):
  [1] Shell Execution         -- CVE-2026-25253/25157
  [2] Skill & Agent Mgmt      -- ClawHavoc 341 malicious skills
  [3] External Messaging       -- Moltbook breach
  [4] Automation & Gateway     -- persistence, gateway exploitation
  [5] Cross-Group Chains       -- primary exfiltration pattern
  [6] File System Operations   -- credential theft
  [7] Web & Network            -- exfiltration, prompt injection
  [8] Agent Orchestration      -- lateral movement (Russell H10)
  [9] Safe Operations Baseline -- proving TELOS allows normal work

Run:
  python3 demos/openclaw_launcher.py
  DEMO_FAST=1 python3 demos/openclaw_launcher.py
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
from openclaw_scenarios import CONFIG_ORDER, CONFIG_DISPLAY


def _show_menu():
    """Display the interactive demo selection menu."""
    print()
    print(_c("  TELOS OpenClaw Governance Demos", "cyan", bold=True))
    print(_c("  9 governance surfaces \u2014 90 scenarios from documented CVEs", "dim"))
    print("  {}".format(_c("\u2500" * 58, "dim")))

    for i, config_id in enumerate(CONFIG_ORDER, 1):
        display = CONFIG_DISPLAY[config_id]
        num = _c("[{}]".format(i), "cyan", bold=True)
        name = _c(display["short_name"], "white", bold=True)
        tag = _c(display["tagline"], "dim")
        print("  {} {}".format(num, name))
        print("      {}".format(tag))

    print("  {}".format(_c("\u2500" * 58, "dim")))
    print("  {} Run ALL demos sequentially (90 scenarios)".format(
        _c("[10]", "cyan", bold=True)))
    print("  {} Exit".format(_c("[0]", "cyan", bold=True)))
    print()


def main(output_dir=None):
    """Interactive launcher for OpenClaw demos."""
    from openclaw_live_demo import main as run_demo

    n_groups = len(CONFIG_ORDER)

    while True:
        _show_menu()

        try:
            raw = input("  Select demo [0-{}]: ".format(n_groups + 1)).strip()
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
        elif 1 <= choice <= n_groups:
            config_id = CONFIG_ORDER[choice - 1]
            display = CONFIG_DISPLAY[config_id]
            print()
            print("  {}".format(_c(
                "Launching: {}".format(display["short_name"]), "green")))
            print()
            run_demo(config_id, output_dir)
        elif choice == n_groups + 1:
            print()
            print("  {}".format(_c(
                "Running all {} OpenClaw demos sequentially ...".format(n_groups), "green")))
            print()
            for config_id in CONFIG_ORDER:
                display = CONFIG_DISPLAY[config_id]
                print()
                print("  {}".format(_c(
                    "=== {} ===".format(display["short_name"]), "cyan", bold=True)))
                run_demo(config_id, output_dir)
            print()
            print("  {}".format(_c(
                "All {} OpenClaw demos completed.".format(n_groups), "green")))
        else:
            print("  {}".format(_c("Invalid selection (0-{})".format(n_groups + 1), "red")))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="TELOS OpenClaw Demo Launcher",
        epilog="Environment variables: DEMO_FAST=1 (skip pauses), DEMO_OBSERVE=1 (extended pauses)",
    )
    parser.add_argument("--output", "-o", default=None,
                        help="Delivery folder for artifacts")
    parser.add_argument("--fast", action="store_true",
                        help="Skip pauses between scenarios (equivalent to DEMO_FAST=1)")
    parser.add_argument("--observe", action="store_true",
                        help="Extended pauses for audience demos (equivalent to DEMO_OBSERVE=1)")
    parser.add_argument("--list", action="store_true",
                        help="List available demo groups and exit (for scripting)")
    args = parser.parse_args()

    # CLI flags mirror environment variables
    if args.fast:
        os.environ["DEMO_FAST"] = "1"
    if args.observe:
        os.environ["DEMO_OBSERVE"] = "1"

    if args.list:
        for i, config_id in enumerate(CONFIG_ORDER, 1):
            display = CONFIG_DISPLAY[config_id]
            print(f"{i:>2}. {config_id:30s} {display['short_name']}")
        sys.exit(0)

    main(args.output)
