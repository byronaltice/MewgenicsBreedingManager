#!/usr/bin/env python3
"""
Mewgenics Breeding Manager — backwards-compatible entry point.

The application has been refactored into the ``mewgenics`` package.
This file is kept so that existing launch methods (run.bat, pyinstaller
spec, etc.) continue to work.
"""
import sys
from mewgenics.app import main

if __name__ == "__main__":
    sys.exit(main())
