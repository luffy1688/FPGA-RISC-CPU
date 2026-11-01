#!/usr/bin/env python3
"""Bit-exact reference for the first XND kernel.

The FPGA unit treats each 32-bit word as four signed int8 lanes and returns
an int32 accumulation. This script is intentionally small so a beginner
can compare it with xnd_dot4.sv and later use the same format for GEMV.
"""
from __future__ import annotations
import argparse
import struct
from typing import Iterable

def lanes(word: int) -> list[int]:
    return [struct.unpack("b", bytes([(word >> (8 * i)) & 0xFF]))[0] for i in range(4)]

def dot4(a_word: int, b_word: int) -> int:
    return sum(a * b for a, b in zip(lanes(a_word), lanes(b_word)))

def pack(values: Iterable[int]) -> int:
    values = list(values)
    if len(values) != 4 or any(not -128 <= x <= 127 for x in values):
        raise ValueError("expected exactly four int8 values")
    return sum((x & 0xFF) << (8 * i) for i, x in enumerate(values))

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--a", type=lambda x: int(x, 0), default=0x01020304)
    parser.add_argument("--b", type=lambda x: int(x, 0), default=0x05060708)
    args = parser.parse_args()
    print(f"a_lanes={lanes(args.a)}")
    print(f"b_lanes={lanes(args.b)}")
    print(f"dot4={dot4(args.a, args.b)}")

if __name__ == "__main__":
    main()
