"""Entry point used when building the exe (PyInstaller needs a plain script)."""

import sys

from aegis_reconnect.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
