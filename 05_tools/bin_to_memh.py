#!/usr/bin/env python3
"""Convert a little-endian firmware binary into one 32-bit word per line."""
from pathlib import Path
import sys

src, dst = map(Path, sys.argv[1:3])
data = src.read_bytes()
data += bytes((-len(data)) % 4)
dst.write_text("\n".join(f"{int.from_bytes(data[i:i+4], 'little'):08x}"
                         for i in range(0, len(data), 4)) + "\n")
