#!/usr/bin/env python3
"""Root entrypoint delegating to src/mobile_scraper.py."""
import os
import sys

SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from mobile_scraper import *
from mobile_scraper import main

if __name__ == "__main__":
    main()
