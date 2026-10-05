"""Backwards-compatible entry point. Prefer: juggernaut --mission ... / python -m juggernaut"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from juggernaut.cli import main

if __name__ == "__main__":
    main()
