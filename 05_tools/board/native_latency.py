#!/usr/bin/env python3
"""Direct Win32 UART latency capture; no pyserial, polling or timer changes.

t0write: immediately before WriteFile; twrite: WriteFile completion (host queue,
not final UART stop bit). RX times are perf_counter_ns timestamps immediately
after ReadFile returns, hence host-observed chunk completion, not wire edges.
The reader is armed before any write. No file writes occur in the timed loop.
Run --selftest on any host. Live capture requires Windows and explicit handoff
(--assume-ready) or an actual boot NR_READY received by this process.
"""
import argparse
import ctypes as C
import datetime
import json
import math
import os
from pathlib import Path
import queue
import statistics
import struct
import sys
import threading
import time

FAST_FIELDS = ("version case config selected_tool decode argument operation "
               "selection_source execute value decision_cycles tool_cycles "
               "request_cycles receipt_kind receipt_requested receipt_readback "
               "receipt_match receipt_period receipt_high receipt_enabled").split()
CONTEXT_FAST_FIELDS = FAST_FIELDS + "context_used context_deny context_logit0 context_logit1 context_threshold".split()
CONTEXT_XND_FAST_FIELDS = CONTEXT_FAST_FIELDS + "context_xnd_used context_loads context_jobs context_dma_read_bytes context_dma_write_bytes context_engine_cycles".split()
DEFAULT_COMMANDS = [
    {"text": "led 37", "tool": 4, "execute": 0, "value": 37},
    {"text": "pwm 20", "tool": 1, "execute": 0, "value": 20},
    {"text": "read temperature", "tool": 0, "execute": 0},
    {"text": "led 256", "tool": 5, "execute": 1},
]



def crc16_ccitt_false(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def encode_request(text, seq):
    payload = text.encode("utf-8")
    if not 1 <= len(payload) <= 64 or any(c in text for c in ("\r", "\n", "\0")):
        raise ValueError("framed request needs 1..64 UTF8 bytes without LF/CR/NUL")
    if not 0 <= seq <= 0xFFFFFFFF:
        raise ValueError("invalid host sequence")
    data = struct.pack("<2sBBHI", b"\xa5\x5a", 1, 0x10, len(payload), seq) + payload
    return data + struct.pack("<H", crc16_ccitt_false(data))


def decode_reply(raw):
    if len(raw) != 64:
        raise ValueError("binary reply must be exactly 64 bytes")
    magic, version, kind, length, seq = struct.unpack_from("<2sBBHI", raw)
    if (magic, version, kind, length) != (b"\xa5\x5a", 1, 0x21, 52):
        raise ValueError("invalid binary reply header/version/type/length")
    expected, = struct.unpack_from("<H", raw, 62)
    actual = crc16_ccitt_false(raw[:62])
    if expected != actual:
        raise ValueError("binary reply CRC mismatch")
    p = raw[10:62]
    operation_source, flags = p[7], p[10]
    if not flags & 0x80:
        raise ValueError("binary reply missing READY flag")
    if flags & 0x60:
        raise ValueError("binary reply has reserved flags")
    context_used, context_deny, context_xnd_used = (flags >> 2) & 1, (flags >> 3) & 1, (flags >> 4) & 1
    if context_deny and not context_used:
        raise ValueError("context deny without a context inference")
    if (p[11] == 0 and (context_used or context_xnd_used) or
            p[11] == 2 and (not context_used or context_xnd_used) or
            p[11] == 3 and (not context_used or not context_xnd_used) or
            context_xnd_used and not context_used):
        raise ValueError("model_used/context flags disagree")
    if bool(operation_source >> 2 == 5) != bool(context_deny) or context_deny and not (p[5] == 5 and p[6] == 8 and p[8] == 1):
        raise ValueError("context veto must be a matched denied execution")
    case, = struct.unpack_from("<I", p)
    argument, = struct.unpack_from("<i", p, 12)
    value, = struct.unpack_from("<i" if p[5] == 0 else "<I", p, 16)
    words = struct.unpack_from("<8I", p, 20)
    fields = ("decision_cycles", "tool_cycles", "request_cycles", "receipt_requested",
              "receipt_readback", "receipt_period", "receipt_high", "uart_status")
    result = dict(zip(fields, words))
    result.update(case=case, config=p[4], selected_tool=p[5], decode=p[6],
                  operation=operation_source & 3, selection_source=operation_source >> 2,
                  execute=p[8], receipt_kind=p[9], receipt_match=flags & 1,
                  receipt_enabled=(flags >> 1) & 1, model_used=p[11],
                  argument=argument, value=value,context_used=context_used,context_deny=context_deny,context_xnd_used=context_xnd_used,encoder_used=int(p[11] == 1))
    if not (0 <= p[4] <= 6 and 0 <= p[5] <= 5 and 0 <= p[6] <= 8
            and result['operation'] <= 2 and result['selection_source'] <= 5
            and p[8] <= 3 and p[9] <= 4 and p[11] <= 3):
        raise ValueError("binary reply enum outside protocol range")
    return {"kind": "NR_BINARY", "request_seq": seq, "data": result,
            "ready": True, "crc16": expected, "text": ""}


def decode_line(raw):
    text = raw.rstrip(b"\r\n").decode("utf-8", errors="strict")
    event = {"kind": "OTHER", "text": text}
    if text == "NR_READY":
        event["kind"] = "NR_READY"
    elif text.startswith("NR_FAST "):
        a = json.loads(text[8:])
        if not isinstance(a, list) or not a or (a[0],len(a)) not in ((1,20),(2,25),(3,31)):
            raise ValueError("invalid NR_FAST version/length")
        if any(type(x) is not int for x in a):
            raise ValueError("NR_FAST fields must be integers")
        fields = FAST_FIELDS if a[0] == 1 else CONTEXT_FAST_FIELDS if a[0] == 2 else CONTEXT_XND_FAST_FIELDS
        result = dict(zip(fields,a))
        if a[0] in (2,3):
            if result['context_used'] != 1 or result['context_deny'] not in (0,1):
                raise ValueError("invalid compact context flag")
            if result['context_deny'] and not result['context_used']:
                raise ValueError("compact context deny without inference")
            if not all(-2147483648 <= result[k] <= 2147483647 for k in ('context_logit0','context_logit1')) or not 0 <= result['context_threshold'] <= 2147483647:
                raise ValueError("compact context logit or threshold out of range")
            if bool(result['selection_source'] == 5) != bool(result['context_deny']) or result['context_deny'] and not (result['selected_tool'] == 5 and result['decode'] == 8 and result['execute'] == 1):
                raise ValueError("compact context veto is not a matched rejection")
            result.update(context_logits=[result['context_logit0'],result['context_logit1']],model_used=2 if a[0]==2 else 3,encoder_used=0,cycles=None)
            if a[0] == 2:result['context_xnd_used']=0
            else:
                if result['context_xnd_used'] != 1 or any(not 0 <= result[k] <= 0xffffffff for k in CONTEXT_XND_FAST_FIELDS[26:]):
                    raise ValueError('invalid compact context XND telemetry')
                result['context_hardware']={k:result['context_'+k]for k in ['loads','jobs','dma_read_bytes','dma_write_bytes','engine_cycles']}
        event.update(kind="NR_FAST", data=result)
    elif text.startswith("NR_RESULT "):
        obj = json.loads(text[10:])
        for key in ("case", "selected_tool", "execute", "value"):
            if type(obj.get(key)) is not int:
                raise ValueError("invalid NR_RESULT " + key)
        event.update(kind="NR_RESULT", data=obj)
    elif text.startswith("NR_") and " " in text:
        kind, _, payload = text.partition(" ")
        event["kind"] = kind
        if payload.startswith(("{", "[")):
            event["data"] = json.loads(payload)
        else:
            event["data"] = payload
    return event


class FrameParser:
    """Mixed text/binary parser; binary payload may contain arbitrary LF bytes."""
    def __init__(self):
        self.pending = bytearray()
        self.allow_startup_noise = False

    def feed(self, chunk, received_ns):
        self.pending.extend(chunk)
        events = []
        while self.pending:
            if self.pending[0] == 0xA5:
                if len(self.pending) < 10:
                    break
                magic, version, kind, length, seq = struct.unpack_from("<2sBBHI", self.pending)
                if (magic, version, kind, length) != (b"\xa5\x5a", 1, 0x21, 52):
                    raise ValueError("invalid binary reply header/version/type/length")
                if len(self.pending) < 64:
                    break
                raw = bytes(self.pending[:64])
                del self.pending[:64]
                event = decode_reply(raw)
            else:
                if b"\n" not in self.pending:
                    break
                end = self.pending.index(10) + 1
                raw = bytes(self.pending[:end])
                del self.pending[:end]
                try:
                    event = decode_line(raw)
                except UnicodeDecodeError:
                    if not self.allow_startup_noise:
                        raise
                    event = {"kind": "BOOT_NOISE", "text": "Invalid bytes during FPGA configuration; raw bytes preserved"}
                if event["kind"] == "NR_BUILD":
                    self.allow_startup_noise = False
            event.update(received_ns=received_ns, wire_bytes=len(raw),
                         raw_hex=raw.hex())
            events.append(event)
        if len(self.pending) > 65536:
            raise ValueError("unterminated frame >64KiB")
        return events

class Win32Serial:
    """Overlapped full-duplex ReadFile with a prearmed dedicated reader thread."""
    def __init__(self, port, baud):
        if os.name != "nt":
            raise OSError("live capture requires Windows")
        DWORD, WORD, BYTE = C.c_uint32, C.c_uint16, C.c_ubyte
        HANDLE, BOOL = C.c_void_p, C.c_int
        class DCB(C.Structure):
            _fields_ = [("DCBlength", DWORD), ("BaudRate", DWORD),
                        ("flags", DWORD), ("wReserved", WORD),
                        ("XonLim", WORD), ("XoffLim", WORD),
                        ("ByteSize", BYTE), ("Parity", BYTE), ("StopBits", BYTE),
                        ("XonChar", C.c_char), ("XoffChar", C.c_char),
                        ("ErrorChar", C.c_char), ("EofChar", C.c_char),
                        ("EvtChar", C.c_char), ("wReserved1", WORD)]
        class Timeouts(C.Structure):
            _fields_ = [(key, DWORD) for key in ("ReadIntervalTimeout",
                "ReadTotalTimeoutMultiplier", "ReadTotalTimeoutConstant",
                "WriteTotalTimeoutMultiplier", "WriteTotalTimeoutConstant")]
        class COMSTAT(C.Structure):
            _fields_ = [("flags", DWORD), ("cbInQue", DWORD), ("cbOutQue", DWORD)]
        class OVERLAPPED(C.Structure):
            _fields_ = [("Internal", C.c_size_t), ("InternalHigh", C.c_size_t),
                        ("Offset", DWORD), ("OffsetHigh", DWORD), ("hEvent", HANDLE)]
        assert C.sizeof(DCB) == 28 and C.sizeof(Timeouts) == 20
        self.DWORD, self.COMSTAT, self.OVERLAPPED = DWORD, COMSTAT, OVERLAPPED
        self.k = C.WinDLL("kernel32", use_last_error=True)
        specs = {
            "CreateFileW": ([C.c_wchar_p, DWORD, DWORD, C.c_void_p, DWORD,
                            DWORD, HANDLE], HANDLE),
            "CloseHandle": ([HANDLE], BOOL),
            "CreateEventW": ([C.c_void_p, BOOL, BOOL, C.c_wchar_p], HANDLE),
            "ResetEvent": ([HANDLE], BOOL),
            "GetOverlappedResult": ([HANDLE, C.POINTER(OVERLAPPED),
                                     C.POINTER(DWORD), BOOL], BOOL),
            "GetCommState": ([HANDLE, C.POINTER(DCB)], BOOL),
            "SetCommState": ([HANDLE, C.POINTER(DCB)], BOOL),
            "GetCommTimeouts": ([HANDLE, C.POINTER(Timeouts)], BOOL),
            "SetCommTimeouts": ([HANDLE, C.POINTER(Timeouts)], BOOL),
            "ReadFile": ([HANDLE, C.c_void_p, DWORD, C.POINTER(DWORD),
                          C.c_void_p], BOOL),
            "WriteFile": ([HANDLE, C.c_void_p, DWORD, C.POINTER(DWORD),
                           C.c_void_p], BOOL),
            "ClearCommError": ([HANDLE, C.POINTER(DWORD), C.POINTER(COMSTAT)], BOOL),
        }
        for name, (args, result) in specs.items():
            getattr(self.k, name).argtypes = args
            getattr(self.k, name).restype = result
        self.handle = self.k.CreateFileW("\\\\.\\" + port, 0xC0000000,
                                        0, None, 3, 0x40000000, None)
        if self.handle == C.c_void_p(-1).value:
            raise C.WinError(C.get_last_error())
        self.original_dcb, self.original_timeouts = DCB(), Timeouts()
        self.original_dcb.DCBlength = C.sizeof(DCB)
        self.read_event = self.k.CreateEventW(None, True, False, None)
        self.write_event = self.k.CreateEventW(None, True, False, None)
        self.reader = None
        self.stop = threading.Event()
        self.queue = queue.Queue()
        self.armed = threading.Event()
        try:
            self.check(self.read_event and self.write_event)
            self.check(self.k.GetCommState(self.handle, C.byref(self.original_dcb)))
            self.check(self.k.GetCommTimeouts(self.handle, C.byref(self.original_timeouts)))
            dcb = DCB()
            dcb.DCBlength, dcb.BaudRate = C.sizeof(DCB), baud
            dcb.flags, dcb.ByteSize, dcb.Parity, dcb.StopBits = 1, 8, 0, 0
            self.check(self.k.SetCommState(self.handle, C.byref(dcb)))
            # Documented first-byte-return blocking mode, no periodic sleep.
            # 250ms only bounds idle shutdown; data returns immediately.
            timeout = Timeouts(0xFFFFFFFF, 0xFFFFFFFF, 250, 0, 2000)
            self.check(self.k.SetCommTimeouts(self.handle, C.byref(timeout)))
            actual = DCB()
            actual.DCBlength = C.sizeof(DCB)
            self.check(self.k.GetCommState(self.handle, C.byref(actual)))
            self.settings = {"baud": actual.BaudRate, "byte_size": actual.ByteSize,
                             "parity": actual.Parity, "stop_bits": actual.StopBits,
                             "dcb_flags": actual.flags,
                             "read_timeouts": [0xFFFFFFFF, 0xFFFFFFFF, 250],
                             "dtr": False, "rts": False, "handshake": "none"}
            self.reader = threading.Thread(target=self._read, daemon=True)
            self.reader.start()
            if not self.armed.wait(2):
                raise TimeoutError("reader did not arm")
        except BaseException:
            self.close()
            raise

    @staticmethod
    def check(ok):
        if not ok:
            raise C.WinError(C.get_last_error())

    def _complete(self, ok, overlapped, count):
        if not ok:
            error = C.get_last_error()
            if error != 997:  # ERROR_IO_PENDING
                raise C.WinError(error)
        self.check(self.k.GetOverlappedResult(
            self.handle, C.byref(overlapped), C.byref(count), True))

    def _read(self):
        buf = C.create_string_buffer(4096)
        count = self.DWORD()
        overlapped = self.OVERLAPPED()
        overlapped.hEvent = self.read_event
        try:
            while not self.stop.is_set():
                self.check(self.k.ResetEvent(self.read_event))
                ok = self.k.ReadFile(self.handle, buf, 4096, C.byref(count),
                                     C.byref(overlapped))

                pending_error = C.get_last_error() if not ok else 0
                # The native read is now actually pending (or complete).
                self.armed.set()
                if not ok and pending_error != 997:
                    raise C.WinError(pending_error)
                self._complete(ok, overlapped, count)
                received_ns = time.perf_counter_ns()
                if count.value:
                    self.queue.put((received_ns, bytes(buf.raw[:count.value])))
        except BaseException as exc:
            self.queue.put(exc)

    def write(self, data):
        count = self.DWORD()
        buf = C.create_string_buffer(data)
        overlapped = self.OVERLAPPED()
        overlapped.hEvent = self.write_event
        self.check(self.k.ResetEvent(self.write_event))
        t0 = time.perf_counter_ns()
        ok = self.k.WriteFile(self.handle, buf, len(data), C.byref(count),
                              C.byref(overlapped))
        self._complete(ok, overlapped, count)
        done = time.perf_counter_ns()
        if count.value != len(data):
            raise IOError("partial WriteFile: %s/%s" % (count.value, len(data)))
        return t0, done

    def errors(self):
        errors, stat = self.DWORD(), self.COMSTAT()
        self.check(self.k.ClearCommError(self.handle, C.byref(errors), C.byref(stat)))
        return {"error_flags": errors.value, "input_queue": stat.cbInQue,
                "output_queue": stat.cbOutQue}

    def close(self):
        self.stop.set()
        if self.reader is not None:
            self.reader.join(1.0)
            if self.reader.is_alive():
                # Keep the object/handle alive; do not race CloseHandle with IO.
                raise RuntimeError("reader failed to stop after blocking read timeout")
        if getattr(self, "handle", None) is not None:
            self.k.SetCommTimeouts(self.handle, C.byref(self.original_timeouts))
            self.k.SetCommState(self.handle, C.byref(self.original_dcb))
            self.k.CloseHandle(self.handle)
            self.handle = None
        for name in ("read_event", "write_event"):
            event = getattr(self, name, None)
            if event:
                self.k.CloseHandle(event)
                setattr(self, name, None)


class Runner:
    def __init__(self, serial, evidence, timeout, protocol="text"):
        self.serial, self.evidence = serial, evidence
        self.protocol, self.next_request_seq = protocol, 1
        self.parser, self.timeout = FrameParser(), timeout
        self.ready, self.sequence = False, None

    def receive(self, deadline):
        remaining = (deadline - time.perf_counter_ns()) / 1e9
        if remaining <= 0:
            raise TimeoutError("response deadline expired")
        try:
            item = self.serial.queue.get(timeout=remaining)
        except queue.Empty:
            raise TimeoutError("no response by deadline")
        if isinstance(item, BaseException):
            raise item
        received_ns, chunk = item
        index = len(self.evidence["rx_chunks"])
        self.evidence["rx_chunks"].append(
            {"received_ns": received_ns, "hex": chunk.hex()})
        return index, received_ns, self.parser.feed(chunk, received_ns)

    def wait_ready(self):
        deadline = time.perf_counter_ns() + int(self.timeout * 1e9)
        while not self.ready:
            index, _, events = self.receive(deadline)
            self.evidence["initial_rx"].append({"chunk": index, "events": events})
            for event in events:
                if event["kind"] in ("NR_BUILD", "OTHER") and event["text"].startswith(
                        ("NeedleRV-X ", "NR_BUILD ")):
                    self.ready = False
                if event["kind"] == "NR_READY":
                    self.ready = True

    def request(self, text, phase, expected=None):
        if not self.ready:
            raise RuntimeError("refusing write before NR_READY or explicit handoff")
        framed = self.protocol == "framed" and not text.startswith(":")
        seq = self.next_request_seq if framed else None
        data = encode_request(text, seq) if framed else text.encode("utf-8") + b"\n"
        if (not framed and len(data) > 65) or "\r" in text or "\n" in text:
            raise ValueError("command must fit one <=64-byte UTF8 line")
        sample = {"text": text, "phase": phase, "tx_hex": data.hex(),
                  "protocol": "framed" if framed else "text", "request_seq": seq,
                  "rx_chunks": [], "events": [], "validation": []}
        if framed:
            self.next_request_seq = (seq + 1) & 0xFFFFFFFF
        self.evidence["samples"].append(sample)
        self.ready = False
        sample["t0write_ns"], sample["twrite_ns"] = self.serial.write(data)
        deadline = sample["t0write_ns"] + int(self.timeout * 1e9)
        while not self.ready:
            index, received_ns, events = self.receive(deadline)
            sample["rx_chunks"].append(index)
            if received_ns < sample["t0write_ns"]:
                raise RuntimeError("stale queued RX precedes this write")
            sample.setdefault("tfirst_ns", received_ns)
            for event in events:
                sample["events"].append(event)
                kind = event["kind"]
                if kind in ("NR_BUILD", "NR_BACKEND_ERROR"):
                    raise RuntimeError("board restart/backend failure during request")
                if kind in ("NR_FAST", "NR_RESULT", "NR_BINARY"):
                    result = event["data"]
                    if framed and kind == "NR_RESULT":
                        if "full_result" in sample:
                            raise RuntimeError("multiple full neural results")
                        sample["full_result"] = result
                        sample["tmodel_frame_ns"] = received_ns
                        continue
                    if framed and kind != "NR_BINARY":
                        raise RuntimeError("ASCII compact result for framed request")
                    if not framed and kind == "NR_BINARY":
                        raise RuntimeError("unsolicited binary reply")
                    if "result" in sample:
                        raise RuntimeError("multiple result frames in one request")
                    if framed:
                        if event["request_seq"] != seq:
                            raise RuntimeError("request sequence mismatch expected=%s actual=%s" %
                                               (seq, event["request_seq"]))
                        if ("full_result" in sample and
                                sample["full_result"]["case"] != result["case"]):
                            raise RuntimeError("neural ASCII and binary case disagree")
                        if "full_result" in sample:
                            for key in ('model_used','context_used','context_deny','context_xnd_used'):
                                if key in sample['full_result'] and sample['full_result'][key] != result[key]:
                                    raise RuntimeError("full/binary execution-path mismatch: " + key)
                        if result["model_used"] == 1 and "full_result" not in sample:
                            raise RuntimeError("binary says full encoder used but full telemetry missing")
                    case = result["case"]
                    if self.sequence is not None and case != self.sequence:
                        raise RuntimeError("case sequence mismatch expected=%s actual=%s" %
                                           (self.sequence, case))
                    self.sequence = (case + 1) & 0xFFFFFFFF
                    sample["result"] = result
                    sample["tframe_ns"] = received_ns
                    if framed:
                        sample["tready_ns"] = received_ns
                        self.ready = True
                elif kind == "NR_IO":
                    sample["io"] = event["data"]
                    sample["tframe_ns"] = received_ns
                elif kind == "NR_LINK":
                    sample["link"] = event["data"]
                    sample["tframe_ns"] = received_ns
                elif kind == "NR_READY":
                    sample["tready_ns"] = received_ns
                    self.ready = True
                    if framed:
                        sample["framed_error_ready"] = True
        if sample.get("framed_error_ready"):
            raise RuntimeError("framed request returned ASCII error/READY; no automatic retry")
        if self.parser.pending:
            raise RuntimeError("unexpected trailing bytes after READY")
        for key in ("twrite", "tfirst", "tframe", "tready"):
            stamp = sample.get(key + "_ns")
            sample[key + "_ms"] = None if stamp is None else (
                stamp - sample["t0write_ns"]) / 1e6
        if text == ":link" and "link" not in sample:
            raise RuntimeError(":link did not return NR_LINK")
        if text == ":io" and "io" not in sample:
            raise RuntimeError(":io did not return NR_IO")
        if not text.startswith(":") and "result" not in sample:
            raise RuntimeError("READY without complete result frame")
        if expected:
            result = sample.get("result", {})
            for source, target in (("tool", "selected_tool"), ("execute", "execute"),
                                   ("value", "value")):
                if source in expected:
                    passed = result.get(target) == expected[source]
                    sample["validation"].append(
                        {"field": target, "expected": expected[source],
                         "actual": result.get(target), "passed": passed})
                    if not passed:
                        raise AssertionError("unexpected %s for %r" % (target, text))
            receipt = result.get("receipt")
            if result.get("receipt_kind"):
                if result["receipt_match"] != 1:
                    raise AssertionError("compact register receipt mismatch")
            elif receipt and receipt.get("kind") and receipt.get("match") != 1:
                raise AssertionError("full register receipt mismatch")
        sample["validated"] = True
        return sample


def summary(samples):
    groups = {}
    for sample in samples:
        if sample["phase"] != "measure":
            continue
        entry = groups.setdefault(sample["text"], [])
        entry.append(sample)
    result = {}
    for text, rows in groups.items():
        metrics = {}
        for key in ("twrite_ms", "tfirst_ms", "tframe_ms", "tready_ms"):
            values = [row[key] for row in rows if row.get(key) is not None]
            if not values:
                continue
            ordered = sorted(values)
            metrics[key] = {"n": len(values), "median": statistics.median(values),
                            "min": min(values), "max": max(values),
                            "empirical_p95_nearest_rank":
                                ordered[max(0, math.ceil(.95 * len(ordered)) - 1)],
                            "all_samples": values}
        result[text] = {"validated_samples": sum(row.get("validated") is True for row in rows), "metrics": metrics}
    return result


def selftest():
    fast = [1, 7, 6, 4, 0, 37, 0, 2, 0, 37, 100, 20, 120,
            1, 37, 37, 1, 40500, 8100, 1]
    stream = (b"NR_IO {\"led_mask\":37}\nNR_FAST " +
              json.dumps(fast, separators=(",", ":")).encode() +
              b"\nNR_READY\n")
    for split in range(len(stream) + 1):
        parser = FrameParser()
        got = parser.feed(stream[:split], 11) + parser.feed(stream[split:], 22)
        assert [x["kind"] for x in got] == ["NR_IO", "NR_FAST", "NR_READY"]
        assert got[1]["data"]["case"] == 7
        assert got[1]["data"]["receipt_readback"] == 37
        assert not parser.pending
    parser = FrameParser()
    one_byte = []
    for b in stream:
        one_byte.extend(parser.feed(bytes([b]), 33))
    assert len(one_byte) == 3
    negative = list(fast)
    negative[3], negative[9] = 0, -2345
    assert decode_line(b"NR_FAST " + json.dumps(negative).encode())["data"]["value"] == -2345
    full = b'NR_RESULT {"case":8,"selected_tool":5,"execute":1,"value":0}\r\n'
    assert decode_line(full)["data"]["case"] == 8

    for bad in (b"NR_FAST [1,2]", b"NR_FAST true",
                b'NR_RESULT {"case":true,"selected_tool":0,"execute":0,"value":0}'):
        try:
            decode_line(bad)
        except (ValueError, TypeError, AttributeError):
            pass
        else:
            raise AssertionError("malformed result accepted")
    class FakeSerial:
        def __init__(self):
            self.queue, self.sequence = queue.Queue(), 7
        def write(self, data):
            t0 = time.perf_counter_ns()
            a = list(fast)
            a[1] = self.sequence
            self.sequence += 1
            self.queue.put((t0 + 100, b"NR_FAST " + json.dumps(a).encode() + b"\nNR_RE"))
            self.queue.put((t0 + 200, b"ADY\n"))
            return t0, t0 + 50
    evidence = {"rx_chunks": [], "samples": [], "initial_rx": []}
    runner = Runner(FakeSerial(), evidence, 1)
    runner.ready = True
    for _ in range(10):
        sample = runner.request("led 37", "measure", DEFAULT_COMMANDS[0])
        assert sample["tready_ns"] > sample["tframe_ns"]
    assert summary(evidence["samples"])["led 37"]["metrics"]["tready_ms"]["n"] == 10
    assert len(evidence["rx_chunks"]) == 20
    assert crc16_ccitt_false(b"123456789") == 0x29B1
    request = encode_request("led 37", 0x12345678)
    assert struct.unpack_from("<2sBBHI", request) == (b"\xa5\x5a", 1, 0x10, 6, 0x12345678)
    assert request[10:-2] == b"led 37"
    assert struct.unpack_from("<H", request, len(request)-2)[0] == crc16_ccitt_false(request[:-2])
    for invalid, seq in (("", 1), ("x" * 65, 1), ("led\n37", 1), ("led\0 37", 1), ("led 37", -1)):
        try:
            encode_request(invalid, seq)
        except ValueError:
            pass
        else:
            raise AssertionError("bad request accepted")
    def make_reply(seq, case=7, model_used=0, tool=4, value=37):
        payload = bytearray(52)
        struct.pack_into("<I", payload, 0, case)
        payload[4:12] = bytes([6, tool, 0, 2 << 2, 0, 1, 0x83, model_used])
        struct.pack_into("<ii8I", payload, 12, 37, value,
                         0x0A0A0A0A, 20, 120, 37, 37, 40500, 8100, 0)
        frame = struct.pack("<2sBBHI", b"\xa5\x5a", 1, 0x21, 52, seq) + payload
        return frame + struct.pack("<H", crc16_ccitt_false(frame))
    reply = make_reply(1)
    got = decode_reply(reply)
    assert got["request_seq"] == 1 and got["data"]["value"] == 37
    assert decode_reply(make_reply(2, tool=0, value=-1234))["data"]["value"] == -1234
    assert decode_reply(make_reply(3, tool=3, value=-1))["data"]["value"] == 0xFFFFFFFF
    assert got["data"]["decision_cycles"] == 0x0A0A0A0A
    full_neural = b'NR_RESULT {"case":7,"selected_tool":4,"execute":0,"value":37}\n'
    mixed = full_neural + make_reply(1, model_used=1)
    for split in range(len(mixed) + 1):
        p = FrameParser()
        events = p.feed(mixed[:split], 100) + p.feed(mixed[split:], 200)
        assert [x["kind"] for x in events] == ["NR_RESULT", "NR_BINARY"]
        assert not p.pending
    p = FrameParser()
    events = []
    for byte in mixed:
        events.extend(p.feed(bytes([byte]), 300))
    assert len(events) == 2
    def repair_crc(raw):
        return bytes(raw[:-2]) + struct.pack("<H", crc16_ccitt_false(raw[:-2]))
    corrupt_crc = bytearray(reply)
    corrupt_crc[30] ^= 1
    corrupt_length = bytearray(reply)
    corrupt_length[4] = 51
    missing_ready = bytearray(reply)
    missing_ready[20] &= 0x7F
    for bad in (bytes(corrupt_crc), repair_crc(corrupt_length), repair_crc(missing_ready)):
        try:
            FrameParser().feed(bad, 400)
        except ValueError:
            pass
        else:
            raise AssertionError("bad binary response accepted")
    class FakeFramed:
        def __init__(self, fault=None, neural=False):
            self.queue, self.case = queue.Queue(), 7
            self.fault, self.neural = fault, neural
        def write(self, data):
            t0 = time.perf_counter_ns()
            _, _, kind, length, seq = struct.unpack_from("<2sBBHI", data)
            assert kind == 0x10 and len(data) == length + 12
            assert crc16_ccitt_false(data[:-2]) == struct.unpack_from("<H", data, len(data)-2)[0]
            wire = make_reply(seq - 1 if self.fault == "old_seq" else seq,
                              self.case, int(self.neural))
            if self.neural:
                wire = full_neural + wire
            if self.fault == "duplicate_reply":
                wire += wire
            self.queue.put((t0 + 100, wire[:31]))
            self.queue.put((t0 + 200, wire[31:]))
            if self.fault != "old_case":
                self.case += 1
            return t0, t0 + 50
    def framed_runner(fake):
        e = {"rx_chunks": [], "samples": [], "initial_rx": []}
        r = Runner(fake, e, 1, "framed")
        r.ready = True
        return r
    r = framed_runner(FakeFramed())
    for _ in range(10):
        sample = r.request("led 37", "measure", {"tool": 4, "execute": 0, "value": 37})
        assert sample["tframe_ns"] == sample["tready_ns"]
    r = framed_runner(FakeFramed(neural=True))
    sample = r.request("led 37", "validation")
    assert "full_result" in sample and sample["result"]["model_used"] == 1
    for fault in ("old_seq", "old_case", "duplicate_reply"):
        r = framed_runner(FakeFramed(fault))
        try:
            r.request("led 37", "validation")
            if fault == "old_case":
                r.request("led 37", "validation")
        except RuntimeError:
            pass
        else:
            raise AssertionError("sequence/duplicate fault accepted: " + fault)
    class ErrorFramed(FakeFramed):
        def write(self, data):
            t0 = time.perf_counter_ns()
            self.queue.put((t0+100, b"NR_INPUT_ERROR framed_crc\nNR_READY\n"))
            return t0, t0+50
    r = framed_runner(ErrorFramed())
    try:
        r.request("led 37", "validation")
    except RuntimeError:
        assert r.ready and len(r.evidence["samples"]) == 1
    else:
        raise AssertionError("error/READY treated as successful frame")
    context_fast = [2] + fast[1:] + [1,0,-17,46,16]
    event = decode_line(b'NR_FAST '+json.dumps(context_fast).encode())['data']
    assert event['model_used'] == 2 and event['encoder_used'] == 0 and event['context_logits'] == [-17,46]
    context_deny = list(context_fast)
    context_deny[3:10] = [5,8,0,0,5,1,0]
    context_deny[21:24] = [1,90,-4]
    assert decode_line(b'NR_FAST '+json.dumps(context_deny).encode())['data']['context_deny'] == 1
    def modified_reply(frame,fields):
        b=bytearray(frame)
        for offset,value in fields.items():b[offset]=value
        return repair_crc(b)
    ctx_reply = modified_reply(make_reply(1,model_used=2),{20:0x87})
    ctx_result=decode_reply(ctx_reply)['data']
    assert ctx_result['context_used'] == 1 and ctx_result['context_deny'] == 0 and ctx_result['encoder_used'] == 0
    veto_reply=modified_reply(make_reply(1,model_used=2,tool=5,value=0),{16:8,17:5<<2,18:1,19:0,20:0x8c})
    veto=decode_reply(veto_reply)['data'];assert veto['selection_source'] == 5 and veto['context_deny'] == 1
    # Full encoder diagnostics may still run after a context veto with fast=0.
    decode_reply(modified_reply(veto_reply,{21:1}))
    for frame in [modified_reply(ctx_reply,{20:0x97}),modified_reply(ctx_reply,{20:0x8b}),modified_reply(ctx_reply,{20:0x83}),modified_reply(ctx_reply,{21:0}),modified_reply(ctx_reply,{17:5<<2}),modified_reply(ctx_reply,{20:0x8f})]:
        try:decode_reply(frame)
        except ValueError:pass
        else:raise AssertionError('invalid context flags/path accepted')
    for bad in [context_fast[:-1],context_fast+[1],[3]+context_fast[1:]]:
        try:decode_line(b'NR_FAST '+json.dumps(bad).encode())
        except ValueError:pass
        else:raise AssertionError('invalid compact v2 accepted')
    v3 = [3]+context_fast[1:]+[1,5,5,16720,300,5018]
    xnd = decode_line(b'NR_FAST '+json.dumps(v3).encode())['data']
    assert xnd['model_used']==3 and xnd['encoder_used']==0 and xnd['context_xnd_used']==1
    assert xnd['context_hardware']['jobs']==5 and xnd['cycles'] is None
    assert 'failures' not in xnd['context_hardware'] and 'logits' not in xnd
    xr=decode_reply(modified_reply(ctx_reply,{20:0x97,21:3}))['data']
    assert xr['model_used']==3 and xr['context_xnd_used']==1 and 'context_hardware' not in xr
    decode_reply(modified_reply(ctx_reply,{20:0x97,21:1}))
    for bad3 in [v3[:-1],v3+[1],v3[:25]+[0]+v3[26:],v3[:26]+[-1]+v3[27:]]:
        try:decode_line(b'NR_FAST '+json.dumps(bad3).encode())
        except ValueError:pass
        else:raise AssertionError('invalid compactv3 accepted')
    for bad3 in [modified_reply(ctx_reply,{20:0x87,21:3}),modified_reply(ctx_reply,{20:0x97,21:0}),modified_reply(ctx_reply,{20:0xa7,21:3})]:
        try:decode_reply(bad3)
        except ValueError:pass
        else:raise AssertionError('invalid context XND/model flags accepted')
    class ContextFramed:
        def __init__(self):self.queue=queue.Queue()
        def write(self,data):
            t0=time.perf_counter_ns();seq=struct.unpack_from('<I',data,6)[0]
            reply=modified_reply(make_reply(seq,model_used=2),{20:0x87})
            self.queue.put((t0+100,reply[:21]));self.queue.put((t0+200,reply[21:]));return t0,t0+50
    ctx=framed_runner(ContextFramed()).request('led 37','context_only',{'tool':4,'execute':0,'value':37})
    assert ctx['result']['model_used']==2 and 'full_result' not in ctx
    print(json.dumps({"selftest": "PASS", "binary_split_boundaries": len(mixed) + 1,
                      "binary_checks": ["CRC check vector 29B1", "request byte layout",
                          "1..64 UTF8 request bounds", "mixed full-neural and binary reply",
                          "one-byte binary fragmentation with LF in payload",
                          "bad CRC", "bad length", "missing READY", "context-head-only reply without encoder telemetry",
                          "protocol5/6 context veto and reserved/contradictory flags", "NR_FASTv1/v2/v3 compatibility", "context-only XND without encoder telemetry",
                          "wrong host sequence", "duplicate case", "duplicate reply",
                          "ASCII error not success or automatic retry"],
                      "text_split_boundaries": len(stream) + 1,
                      "checks": ["one-byte fragmentation", "signed temperature",
                                 "full result", "malformed rejection",
                                 "ten sequence-correlated request/READY exchanges",
                                 "separate frame and READY timestamps"]}))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--port", default="COM10")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--protocol", choices=("text", "framed"), default="text")
    parser.add_argument("--repeat", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=5)
    parser.add_argument("--output", default="07_runs/development/link_latency/native_text_115200.json")
    parser.add_argument("--commands-json", help="JSON array of text/tool/execute/value specs")
    parser.add_argument("--assume-ready", action="store_true",
                        help="explicit coordinated handoff from known READY, without reset")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.repeat < 10:
        parser.error("--repeat must be >=10 for measured sentence statistics")
    commands = DEFAULT_COMMANDS
    if args.commands_json:
        commands = json.loads(Path(args.commands_json).read_text(encoding="utf-8-sig"))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        parser.error("refusing overwrite of existing raw evidence: " + str(output))
    evidence = {
        "schema": "needlervx.native_latency.v1",
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "clock": dict(time.get_clock_info("perf_counter").__dict__),
        "port": args.port, "baud": args.baud, "repeat": args.repeat, "protocol": args.protocol,
        "method": "Win32 overlapped full-duplex ReadFile event completion dedicated reader, first-byte-return COMMTIMEOUTS",
        "timing_scope": "host WriteFile entry/completion and ReadFile chunk completion; not wire edges",
        "p95_note": "empirical nearest-rank P95; n=10 gives max and is statistically unstable",
        "initial_ready": "explicit coordinated handoff" if args.assume_ready else "wait for actual NR_READY",
        "rx_chunks": [], "initial_rx": [], "samples": [], "failures": [],
    }
    serial, runner, initial = None, None, None
    status = 0
    try:
        serial = Win32Serial(args.port, args.baud)
        evidence["settings"] = serial.settings
        evidence["initial_driver_status"] = serial.errors()
        runner = Runner(serial, evidence, args.timeout, args.protocol)
        runner.ready = args.assume_ready
        if not runner.ready:
            runner.wait_ready()
        if args.protocol == "framed":
            link = runner.request(":link", "initial_link")["link"]
            evidence["initial_link"] = link
            runner.next_request_seq = ((int(link["last_request_seq"]) + 1) & 0xFFFFFFFF
                                       if link["framed_seen"] else 1)
        initial = runner.request(":io", "initial_io")["io"]
        evidence["initial_io"] = initial
        if initial.get("restore_supported") != 1:
            raise RuntimeError("IO snapshot cannot exactly restore active PWM baseline")
        for command in commands:
            phase = command.get("phase", "measure")
            count = command.get("repeat", args.repeat)
            if phase == "measure" and count < 10:
                raise ValueError("measured sentences require >=10 repetitions")
            if phase not in ("measure", "validation") or count < 1:
                raise ValueError("invalid command phase/repeat")
            for _ in range(count):
                runner.request(command["text"], phase, command)
    except BaseException as exc:
        status = 1
        evidence["failures"].append(type(exc).__name__ + ": " + str(exc))
    finally:
        if (runner is not None and initial is not None and runner.ready
                and initial.get("restore_supported") == 1):
            try:
                # Restore exact register state of the coordinated baseline.
                runner.request("led " + str(initial["led_mask"]), "restore",
                               {"tool": 4, "execute": 0, "value": initial["led_mask"]})
                runner.request("pwm " + str(initial["pwm_duty"]), "restore",
                               {"tool": 1, "execute": 0, "value": initial["pwm_duty"]})
                final = runner.request(":io", "final_io")["io"]
                evidence["final_io"] = final
                evidence["io_restored"] = final == initial
                if final != initial:
                    raise AssertionError("final IO snapshot differs from initial")
            except BaseException as exc:
                status = 1
                evidence["failures"].append("restore " + type(exc).__name__ + ": " + str(exc))
        if serial is not None:
            try:
                evidence["final_driver_status"] = serial.errors()
                serial.close()
            except BaseException as exc:
                status = 1
                evidence["failures"].append("close " + type(exc).__name__ + ": " + str(exc))
        evidence["summary"] = summary(evidence["samples"])

        evidence["status"] = "PASS" if status == 0 else "FAIL"
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": evidence["status"], "output": str(output),
                      "io_restored": evidence.get("io_restored"),
                      "failures": evidence["failures"], "summary": evidence["summary"]},
                     ensure_ascii=False))
    return status


if __name__ == "__main__":
    raise SystemExit(main())


