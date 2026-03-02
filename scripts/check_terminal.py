#!/usr/bin/env python3
"""Diagnose terminal graphics capabilities for Aura PDF Reader.

Run this script directly in your terminal (e.g. WezTerm, Kitty, iTerm2)
to see which rendering protocol textual-image detects.

Usage:  python scripts/check_terminal.py
"""

import os
import sys


def main() -> None:
    print("=== Aura Terminal Diagnostics ===\n")
    print(f"Python:        {sys.version}")
    print(f"Platform:      {sys.platform}")
    print(f"stdout is TTY: {sys.__stdout__ and sys.__stdout__.isatty()}")
    print()

    if not (sys.__stdout__ and sys.__stdout__.isatty()):
        print("ERROR: stdout is not a TTY.")
        print("  This script must be run directly in a terminal, not piped or in an IDE.")
        return

    from textual_image.renderable import sixel, tgp

    print("Probing Sixel support (DA1 query, 0.1s timeout)...")
    sixel_ok = sixel.query_terminal_support()
    print(f"  Sixel: {'SUPPORTED' if sixel_ok else 'not detected'}")

    if not sixel_ok:
        print("\nProbing TGP/Kitty support (graphics query, 0.1s timeout)...")
        tgp_ok = tgp.query_terminal_support()
        print(f"  TGP:   {'SUPPORTED' if tgp_ok else 'not detected'}")
    else:
        tgp_ok = False

    # Environment-variable fallback detection (mirrors pdf_viewer.py logic)
    term_program = os.environ.get("TERM_PROGRAM", "")
    term = os.environ.get("TERM", "")
    wt_session = os.environ.get("WT_SESSION", "")
    wezterm_exe = os.environ.get("WEZTERM_EXECUTABLE", "")

    print(f"\nEnvironment hints:")
    print(f"  TERM_PROGRAM:       {term_program or '(not set)'}")
    print(f"  TERM:               {term or '(not set)'}")
    print(f"  WT_SESSION:         {'set' if wt_session else '(not set)'}")
    print(f"  WEZTERM_EXECUTABLE: {'set' if wezterm_exe else '(not set)'}")

    env_hint = None
    if term_program == "WezTerm" or wezterm_exe:
        env_hint = "sixel"
    elif term_program == "iTerm.app":
        env_hint = "sixel"
    elif wt_session:
        env_hint = "sixel"
    elif term_program == "kitty" or term == "xterm-kitty":
        env_hint = "tgp"
    elif "foot" in term:
        env_hint = "sixel"

    print()
    if sixel_ok:
        print("Result: Sixel renderer (pixel-level quality).")
    elif tgp_ok:
        print("Result: TGP/Kitty renderer (pixel-level quality).")
    elif env_hint:
        print(f"Result: Escape-sequence probe failed, but env vars suggest {env_hint.upper()}.")
        print(f"  Aura will auto-select {env_hint.upper()} based on environment detection.")
    else:
        print("Result: No graphics protocol detected. Halfcell character renderer.")
        print()
        print("To force a specific protocol, set the AURA_RENDERER env var:")
        print("  AURA_RENDERER=sixel python -m aura")
        print("  AURA_RENDERER=tgp python -m aura")

    try:
        from textual_image._terminal import get_cell_size
        cell = get_cell_size()
        print(f"\nTerminal cell size: {cell.width}×{cell.height} pixels")
    except Exception as e:
        print(f"\nCould not determine cell size: {e}")


if __name__ == "__main__":
    main()
