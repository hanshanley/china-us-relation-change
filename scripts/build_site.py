#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.model import json_text
from us_china_exchange.render import build


if __name__ == "__main__":
    print(json_text(build(ROOT)), end="")
