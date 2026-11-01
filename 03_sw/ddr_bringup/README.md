# DDR bring-up firmware

This directory contains a deliberately separate firmware pair for the optional
Pangu 200Pro+ DDR path. It does not change the normal BRAM/model image. The
program is linked into the on-chip CPU RAM; all addresses at `0x80000000` are
data transactions only.

## Contract

The integration must instantiate `needle_soc` with `ENABLE_DDR=1`,
`DDR_BASE=0x80000000`, and `DDR_BYTES=0x00100000` (1 MiB). The board-side DDR
subsystem exposes `0x1000010c`: bit 0 means initialized/available, bit 1 is a
sticky bridge fault, and bit 2 means a request is busy. The firmware waits for
bit 0 before touching DDR.

`DDR_BASE..DDR_BASE+DDR_BYTES-4` is the valid aligned CPU/XND data window. The
last word is written and read back. A read at `DDR_BASE+DDR_BYTES` and a read at
`0x10000110` (the first byte after the implemented peripheral map) are
intentional load-access faults. `startup.S` consumes exactly these two traps,
advances `mepc`, and returns; any other trap drives GPIO `0xef`. This is the
software side of the window/hole rejection contract.

## GPIO markers

| marker | meaning |
|---:|---|
| `0x10` | waiting for DDR initialization |
| `0x20` | CPU word/byte/half-word DDR test passed |
| `0x22` | DDR end-boundary and MMIO-hole negative tests passed |
| `0x30` | INT4 activation load/GEMV/reuse passed |
| `0x40` | INT8 activation load/GEMV passed |
| `0xa5` | complete bring-up passed |
| `0xd1` | fault image arms the external response-drop hook |
| `0xa6` | fault/timeout was contained and acknowledged |
| `0xe0..0xe9`, `0xf0`, `0xef` | failure checkpoints |

The XND descriptors deliberately place activation, weights, and outputs in the
DDR window. INT4 and INT8 results are read back by the CPU and compared with a
software golden sum; a guard word after each result catches an overrun. A
second INT4 GEMV reuses the resident activation after its source bytes are
changed, proving LOAD/GEMV residency rather than a software-only calculation.

## Fault image

`fault.mem` runs the same valid sequence, emits `0xd1`, then submits one more
DDR activation load. The integration testbench should drop the next HMIC read
response (or hold it past the configured timeout). The firmware requires an
XND DMA fault/timeout, observes DDR state bit 1, clears XND W1C status, and
finishes at `0xa6`; it deliberately does not submit a new DDR job after the
fault. Because the HMIC interface has no cancel/response channel, recovery is
only by common reset of CPU, bridge, CDC, and DDR controller.

## Build

```bash
make -C 03_sw/ddr_bringup all
```

The 2026-10-03 build produced `07_runs/ddr/bringup.mem` (2,844 bytes text/data
image) and `07_runs/ddr/fault.mem` (3,072 bytes). These are compile artifacts,
not evidence of DDR training, timing closure, or a physical board result.
The latter require the PDS-generated image, the actual HMIC/DDR IP, and the
board test.
