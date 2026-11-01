#!/usr/bin/env python3
"""Physical framed-RPC acceptance using native_latency Win32 IO.

No automatic write retry; one collector owns the COM handle. --selftest does not
open a port. Live use requires an explicit serial handoff. CoreMark runs exactly
once at the requested 900 or1200 iterations, after the capability manifest is checked.
"""
import argparse
import datetime
import json
from pathlib import Path
import re
import struct
import time

from native_latency import (Runner, Win32Serial, crc16_ccitt_false,
                            encode_request)


def ensure(condition, message):
    if not condition:
        raise AssertionError(message)


def make_unchecked_request(payload, sequence, declared_length=None):
    length = len(payload) if declared_length is None else declared_length
    wire = struct.pack("<2sBBHI", b"\xa5\x5a", 1, 0x10, length, sequence) + payload
    return wire + struct.pack("<H", crc16_ccitt_false(wire))


def negative_frames(next_sequence, last_sequence):
    crc_bad = bytearray(encode_request("led 85", next_sequence))
    crc_bad[12] ^= 0x20  # Valid-looking command but corrupt CRC; never re-send.
    return [
        ("bad_crc", bytes(crc_bad), "frame_crc"),
        ("bad_length_65", make_unchecked_request(b"led 85" + b" " * 59,
                                                 next_sequence), "bad_frame"),
        ("bad_length_zero", make_unchecked_request(b"", next_sequence), "bad_frame"),
        ("truncated_frame", encode_request("led 85", next_sequence)[:12],
         "frame_timeout"),
        ("duplicate_sequence", encode_request("led 85", last_sequence),
         "stale_sequence"),
        ("old_sequence", encode_request("pwm 60", (last_sequence - 1) & 0xFFFFFFFF),
         "stale_sequence"),
    ]


def decoded_event(sample, kind):
    items = [event["data"] for event in sample["events"] if event["kind"] == kind]
    ensure(len(items) == 1, "expected exactly one " + kind)
    return items[0]


def assert_uart(sample):
    result = sample["result"]
    status = result["uart_status"]
    # Current hardware UART status bits: TX-ready bit0, RX-ready bit1,
    # overrun sticky bit2. Preserve all bits even when unused.
    sample["uart_status_observed"] = status
    ensure((status & 4) == 0, "UART RX overrun flag")
    frame = [event for event in sample["events"] if event["kind"] == "NR_BINARY"]
    ensure(len(frame) == 1 and frame[0]["wire_bytes"] == 64,
           "framed result must contain exactly one complete 64-byte reply")
    sample["reply_crc16"] = frame[0]["crc16"]
    ensure(frame[0]["request_seq"] == sample["request_seq"], "host sequence echo")


def raw_error(runner, label, wire, expected_error):
    ensure(runner.ready, "negative test requires READY")
    sample = {"phase": "negative", "label": label, "tx_hex": wire.hex(),
              "events": [], "rx_chunks": [], "expected_error": expected_error,
              "request_seq": struct.unpack_from("<I", wire, 6)[0],
              "declared_length": struct.unpack_from("<H", wire, 4)[0],
              "automatic_retry": False}
    if label != "truncated_frame" and len(wire) >= 12:
        sample["tx_crc16_trailer"] = int.from_bytes(wire[-2:], "little")
        sample["tx_crc16_computed_without_trailer"] = crc16_ccitt_false(wire[:-2])
    runner.evidence["samples"].append(sample)
    runner.ready = False
    sample["t0write_ns"], sample["twrite_ns"] = runner.serial.write(wire)
    deadline = sample["t0write_ns"] + int(runner.timeout * 1e9)
    while not runner.ready:
        index, stamp, events = runner.receive(deadline)
        sample["rx_chunks"].append(index)
        ensure(stamp >= sample["t0write_ns"], "stale queued RX in negative test")
        sample.setdefault("tfirst_ns", stamp)
        for event in events:
            sample["events"].append(event)
            ensure(event["kind"] not in ("NR_BINARY", "NR_FAST", "NR_RESULT",
                                         "NR_BUILD", "NR_BACKEND_ERROR"),
                   "negative test executed or board restarted")
            if event["kind"] == "NR_READY":
                runner.ready = True
                sample["tready_ns"] = stamp
    ensure(not runner.parser.pending, "partial trailing data after error READY")
    errors = [event.get("data") for event in sample["events"]
              if event["kind"] == "NR_INPUT_ERROR"]
    ensure(errors == [expected_error], "wrong transport error: " + repr(errors))
    for name in ("twrite", "tfirst", "tready"):
        sample[name + "_ms"] = (sample[name + "_ns"] - sample["t0write_ns"]) / 1e6
    sample["validated"] = True
    return sample


def io_snapshot(runner, phase):
    return runner.request(":io", phase)["io"]


def link_snapshot(runner, phase):
    return runner.request(":link", phase)["link"]


def verify_no_change(runner, initial_io, initial_link, label):
    after_io = io_snapshot(runner, label + "_io_after")
    after_link = link_snapshot(runner, label + "_link_after")
    ensure(after_io == initial_io, label + " changed IO registers")
    ensure(after_link == initial_link, label + " changed accepted request sequence")
    runner.evidence["negative_checks"].append(
        {"label": label, "io_unchanged": True, "link_unchanged": True,
         "io": after_io, "link": after_link})


def restore_io(runner, initial):
    runner.request("led " + str(initial["led_mask"]), "restore",
                   {"tool": 4, "execute": 0, "value": initial["led_mask"]})
    runner.request("pwm " + str(initial["pwm_duty"]), "restore",
                   {"tool": 1, "execute": 0, "value": initial["pwm_duty"]})
    final = io_snapshot(runner, "final_io")
    runner.evidence["final_io"] = final
    ensure(final == initial, "final IO differs from initial")
    runner.evidence["io_restored"] = True


def validate_fallback(sample):
    ensure(sample["result"]["model_used"] == 1, "fallback did not execute model")
    full = sample.get("full_result")
    ensure(isinstance(full, dict) and full.get("model_used") == 1,
           "fallback lacks full NR_RESULT")
    ensure(isinstance(full.get("logits"), list) and len(full["logits"]) == 6,
           "fallback lacks six raw logits")
    ensure(isinstance(full.get("pmu"), dict) and full["pmu"].get("instret", 0) > 0,
           "fallback lacks real PMU telemetry")
    # Full JSON encodes argument/counter words unsigned; framed result uses i32.
    binary = sample["result"]
    for key in ("case", "config", "selected_tool", "decode", "operation",
                "selection_source", "execute", "decision_cycles", "tool_cycles",
                "request_cycles"):
        ensure(full[key] == binary[key], "full/binary mismatch: " + key)
    for key in ("argument", "value"):
        ensure((full[key] & 0xFFFFFFFF) == (binary[key] & 0xFFFFFFFF),
               "full/binary word mismatch: " + key)
    for key in ('context_used','context_deny','context_xnd_used'):
        if key in full:ensure(full[key] == binary.get(key), 'full/binary context mismatch: '+key)
    sample["fallback_full_telemetry_preserved"] = True


def validate_coremark(sample, iterations=900):
    texts = [event["text"] for event in sample["events"]]
    text = "\n".join(texts)
    ensure(sum(line.startswith("Correct operation validated.") for line in texts) == 1,
           "CoreMark validation line missing or repeated")
    match = re.search(r"NR_CYCLES=(\d+) NR_HZ=(\d+) NR_ITERATIONS=(\d+)", text)
    ensure(match is not None and int(match[3]) == iterations,
           "CoreMark iteration count differs from the acceptance contract")
    cycles, hz = int(match[1]), int(match[2])
    ensure(cycles > 0 and hz > 0 and cycles/hz >= 10, "invalid CoreMark timing or run below10seconds")
    ensure((sample["result"]["value"] & 0xFFFFFFFF) == cycles,
           "CoreMark result cycles disagree with raw timing")
    ensure(iterations in (900,1200), "No independently established CRC contract for this iteration count")
    expected = {"seedcrc": "e9f5", "crclist": "e714", "crcmatrix": "1fd7",
                "crcstate": "8e3a", "crcfinal": {900:"4983",1200:"988c"}[iterations]}
    actual = {}
    for key in expected:
        found = re.findall(r"(?:\[0\])?" + key + r"\s*:\s*0x([0-9a-fA-F]+)", text)
        ensure(len(found) == 1, "missing or duplicate CoreMark " + key)
        actual[key] = found[0].lower()
    ensure(actual == expected, "CoreMark CRC evidence differs from the known iteration-specific reference")
    ensure("NR_COREMARK_RETURN" in texts, "CoreMark did not return to caller")
    action = [event["data"] for event in sample["events"] if event["kind"] == "NR_ACTION"]
    ensure(len(action) == 1 and action[0].get("phase") == "tool_start"
           and action[0].get("case") == sample["result"]["case"],
           "missing matched CoreMark start phase")
    sample["coremark"] = {"iterations": iterations, "cycles": cycles, "clock_hz": hz,
                          "crc": actual, "correct_operation_validated": True}


def run_acceptance(runner, expected_iterations=1200):
    evidence = runner.evidence
    manifest_sample = runner.request(":tools", "manifest")
    manifest = decoded_event(manifest_sample, "NR_TOOLS")
    evidence["tool_manifest"] = manifest
    benchmark = [item for item in manifest.get("tools", []) if item.get("id") == 2]
    ensure(len(benchmark) == 1 and benchmark[0].get("iterations") == expected_iterations,
           "firmware manifest does not declare the requested iteration count")
    initial_link = link_snapshot(runner, "initial_link")
    ensure(initial_link["uart_baud"] == evidence["baud"], "configured baud/firmware mismatch")
    runner.next_request_seq = ((initial_link["last_request_seq"] + 1) & 0xFFFFFFFF
                               if initial_link["framed_seen"] else 1)
    initial = io_snapshot(runner, "initial_io")
    evidence["initial_io"], evidence["initial_link"] = initial, initial_link
    ensure(initial.get("restore_supported") == 1,
           "baseline PWM cannot be exactly restored; no functional writes allowed")
    # Establish accepted seq with an idempotent low-risk write; failures never retry.
    base = runner.request("led " + str(initial["led_mask"]), "valid_baseline",
                          {"tool": 4, "execute": 0, "value": initial["led_mask"]})
    assert_uart(base)
    baseline_io = io_snapshot(runner, "baseline_io")
    baseline_link = link_snapshot(runner, "baseline_link")
    ensure(baseline_io == initial, "idempotent baseline write changed IO")
    ensure(baseline_link["last_request_seq"] == base["request_seq"],
           "link last sequence does not match accepted request")
    for label, wire, expected_error in negative_frames(
            runner.next_request_seq, base["request_seq"]):
        before = io_snapshot(runner, label + "_io_before")
        ensure(before == baseline_io, label + " began with unexpected IO")
        raw_error(runner, label, wire, expected_error)
        verify_no_change(runner, before, baseline_link, label)
    # GPIO0 alone changes; all other mask bits must remain identical.
    off_value = initial["led_mask"] & ~1
    off = runner.request("只关闭LED0，其他LED保持不变。", "valid_led_rmw",
                         {"tool": 4, "execute": 0, "value": off_value})
    assert_uart(off)
    ensure(off["result"]["operation"] == 2, "LED off lacks RMW operation")
    after_off = io_snapshot(runner, "led_rmw_io")
    expected_off = dict(initial, led_mask=off_value)
    ensure(after_off == expected_off, "LED RMW changed unrelated GPIO/PWM fields")
    pwm = runner.request("pwm 30", "valid_pwm",
                         {"tool": 1, "execute": 0, "value": 30})
    assert_uart(pwm)
    pwm_io = io_snapshot(runner, "pwm_io")
    ensure(pwm_io["led_mask"] == off_value and pwm_io["pwm_duty"] == 30
           and pwm_io["pwm_high"] == pwm_io["pwm_period"] * 30 // 100
           and pwm_io["pwm_enabled"] == 1, "PWM register readback incorrect")
    runner.request(":fast 0", "force_full_encoder_telemetry")
    fallback = runner.request("你好", "model_fallback")
    assert_uart(fallback)
    validate_fallback(fallback)
    runner.request(":fast 1", "restore_fast_mode")
    ensure(io_snapshot(runner, "fallback_io") == pwm_io,
           "read-only fallback phrase changed IO")
    # One actual invocation. A timeout or failed CRC is recorded without retry.
    evidence["coremark_invocations"] = 1
    old_timeout = runner.timeout
    runner.timeout = 60
    try:
        core = runner.request("run coremark", "coremark_once",
                              {"tool": 2, "execute": 0})
    finally:

        runner.timeout = old_timeout
    assert_uart(core)
    validate_coremark(core, expected_iterations)
    evidence["functional_tests_completed"] = True


def selftest():
    frames = negative_frames(12, 11)
    ensure([x[0] for x in frames] == ["bad_crc", "bad_length_65", "bad_length_zero",
           "truncated_frame", "duplicate_sequence", "old_sequence"], "negative set")
    ensure(len(frames[1][1]) == 77 and struct.unpack_from("<H", frames[1][1], 4)[0] == 65,
           "oversized length test layout")
    ensure(len(frames[2][1]) == 12 and len(frames[3][1]) == 12,
           "zero/truncated layouts")
    ensure(crc16_ccitt_false(frames[0][1][:-2]) != int.from_bytes(frames[0][1][-2:], "little"),
           "bad CRC test not corrupt")
    class Fake:
        def __init__(self, wrong=None):
            import queue
            self.queue, self.writes, self.wrong = queue.Queue(), [], wrong
        def write(self, wire):
            self.writes.append(wire)
            t0 = time.perf_counter_ns()
            text = b"NR_INPUT_ERROR " + (self.wrong or b"frame_crc") + b"\nNR_READY\n"
            self.queue.put((t0+100, text[:15]))
            self.queue.put((t0+200, text[15:]))
            return t0, t0+50
    fake = Fake()
    evidence = {"samples": [], "rx_chunks": [], "initial_rx": [], "negative_checks": []}
    r = Runner(fake, evidence, 1, "framed")
    r.ready = True
    sample = raw_error(r, "bad_crc", frames[0][1], "frame_crc")
    ensure(r.ready and len(fake.writes) == 1 and sample["validated"],
           "negative collector retried or failed")
    fake = Fake(b"wrong_error")
    r = Runner(fake, {"samples": [], "rx_chunks": []}, 1, "framed")
    r.ready = True
    try:
        raw_error(r, "bad_crc", frames[0][1], "frame_crc")
    except AssertionError:
        ensure(len(fake.writes) == 1, "error case retried")
    else:
        raise AssertionError("wrong error accepted")
    core_sample = {"result": {"case": 3, "value": 600000000}, "events": [
        {"kind": "NR_ACTION", "text": "", "data": {"phase": "tool_start", "case": 3}},
        {"kind": "OTHER", "text": "Correct operation validated."},
        {"kind": "OTHER", "text": "NR_CYCLES=600000000 NR_HZ=40500000 NR_ITERATIONS=900"},
        {"kind": "OTHER", "text": "seedcrc : 0xe9f5\n[0]crclist : 0xe714\n[0]crcmatrix : 0x1fd7\n[0]crcstate : 0x8e3a\n[0]crcfinal : 0x4983"},
        {"kind": "OTHER", "text": "NR_COREMARK_RETURN"}]}
    validate_coremark(core_sample)
    core_sample["events"][3]["text"] = core_sample["events"][3]["text"].replace("4983", "5275")
    try:
        validate_coremark(core_sample)
    except AssertionError:
        pass
    else:
        raise AssertionError("wrong CoreMark CRC accepted")
    sample1200=json.loads(json.dumps(core_sample))
    for event in sample1200['events']:event['text']=event['text'].replace('NR_ITERATIONS=900','NR_ITERATIONS=1200').replace('0x5275','0x988c')
    validate_coremark(sample1200,1200)
    assert sample1200['coremark']['iterations']==1200
    print(json.dumps({"selftest": "PASS", "hardware_access": False,
          "checks": ["six negative frame layouts", "CRC corruption", "single raw write no retry",
                     "error/READY fragmentation", "wrong error rejected",
                     "900/1200-iteration CRC parsing", "10second minimum", "wrong CRC rejected"]}))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--port", default="COM10")
    p.add_argument("--baud", type=int, default=921600)
    p.add_argument("--timeout", type=float, default=5)
    p.add_argument("--iterations",type=int,choices=(900,1200),default=1200)
    p.add_argument("--assume-ready", action="store_true")
    p.add_argument("--output", default="07_runs/development/link_latency/framed_rpc_acceptance.json")
    args = p.parse_args()
    if args.selftest:
        return selftest()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        p.error("refusing overwrite of raw evidence")
    evidence = {"schema": "needlervx.framed_rpc_acceptance.v1",
                "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "port": args.port, "baud": args.baud, "samples": [], "rx_chunks": [],
                "initial_rx": [], "negative_checks": [], "failures": [],
                "automatic_write_retry": False}
    serial, runner = None, None
    status = 0
    try:
        serial = Win32Serial(args.port, args.baud)
        evidence["settings"] = serial.settings
        evidence["initial_driver_status"] = serial.errors()
        runner = Runner(serial, evidence, args.timeout, "framed")
        runner.ready = args.assume_ready
        if not runner.ready:
            runner.wait_ready()
        run_acceptance(runner,args.iterations)
    except BaseException as exc:
        status = 1
        evidence["failures"].append(type(exc).__name__ + ": " + str(exc))
    finally:
        initial = evidence.get("initial_io")
        if runner is not None and initial and initial.get("restore_supported") == 1 and runner.ready:
            try:
                restore_io(runner, initial)
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
        evidence["status"] = "PASS" if status == 0 else "FAIL"
        path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": evidence["status"], "output": str(path),
                      "negative_checks": len(evidence["negative_checks"]),
                      "io_restored": evidence.get("io_restored"),
                      "coremark_invocations": evidence.get("coremark_invocations"),
                      "failures": evidence["failures"]}, ensure_ascii=False))
    return status


if __name__ == "__main__":
    raise SystemExit(main())


