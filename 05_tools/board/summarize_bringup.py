#!/usr/bin/env python3
"""Summarize captured serial and PDS evidence without claiming physical IO tests."""
import argparse
import base64
import codecs
import hashlib
import json
import re
from pathlib import Path


def read_text(path):
    data = path.read_bytes()
    encoding = "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    return data.decode(encoding, errors="replace")


def provenance(path):
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def summarize(events_path, program_path):
    serial_info = None
    capture_closed = False
    capture_state = "unknown"
    errors = []
    records = []
    requests = []
    pending = None
    line_buffer = ""
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    rx_bytes = 0
    tx_bytes = 0
    ready_count = 0
    boot_build = None
    coremark_lines = []

    def accept_line(line):
        nonlocal pending, ready_count, boot_build
        if line.startswith(("NR_BUILD ", "NR_CONFIG ", "NR_RESULT ", "NR_PMU ")):
            prefix, payload = line.split(" ", 1)
            try:
                record = {"kind": prefix, "data": json.loads(payload)}
                records.append(record)
                if prefix == "NR_BUILD":
                    boot_build = record["data"]
                if pending is not None:
                    pending["records"].append(record)
            except json.JSONDecodeError as exc:
                errors.append({"kind": "invalid_protocol_json", "line": line, "error": str(exc)})
        if line.startswith(("NR_INPUT_ERROR", "NR_BACKEND_ERROR", "NR_CONTROL_ERROR", "MODEL_ERROR")):
            if pending is not None:
                pending["responses"].append(line)
        if line == "NR_READY":
            ready_count += 1
            if pending is not None:
                pending["ready_returned"] = True
                pending = None
        if any(marker in line for marker in ("CoreMark", "Correct operation validated", "Errors detected", "NR_CYCLES=", "crc", "CRC")):
            coremark_lines.append(line)

    for number, raw_line in enumerate(read_text(events_path).splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            event = json.loads(raw_line)
            direction = event["direction"]
            data = event.get("data")
            if direction == "INFO" and isinstance(data, dict):
                serial_info = data
            elif direction == "RX":
                raw = base64.b64decode(data["bytes_base64"], validate=True)
                rx_bytes += len(raw)
                line_buffer += decoder.decode(raw)
                while "\n" in line_buffer:
                    line, line_buffer = line_buffer.split("\n", 1)
                    accept_line(line.rstrip("\r"))
            elif direction == "TX":
                raw = base64.b64decode(data["bytes_base64"], validate=True)
                tx_bytes += len(raw)
                if pending is not None:
                    errors.append({"kind": "overlapping_tx", "previous_id": pending["id"], "at": event.get("at")})
                pending = {"id": data.get("id"), "text": data.get("text"), "at": event.get("at"),
                           "write_completed": data.get("completed", True), "records": [],
                           "responses": [], "ready_returned": False}
                requests.append(pending)
            elif direction == "CLOSE":
                capture_closed = True
                capture_state = data.get("state", "unknown")
            elif direction in ("ERROR", "COMMAND_ERROR"):
                errors.append({"kind": direction, "at": event.get("at"), "data": data})
        except (ValueError, KeyError, TypeError) as exc:
            errors.append({"kind": "invalid_event", "line_number": number, "error": str(exc)})

    program = read_text(program_path)
    program_success = bool(re.search(r"COMMAND\[Program\] execute successfully", program) and
                           re.search(r"The done bit is 1\b", program))
    status_done_one = bool(re.search(r"Bit 12:\s+1\s+done\b", program))
    model_requests = [r for r in requests if r["ready_returned"] and r["write_completed"] and
                      any(v["kind"] == "NR_RESULT" for v in r["records"])]
    probe_success = any(r["text"] == ":probe" and r["write_completed"] and r["ready_returned"] and
                        "NR_CONTROL_ERROR invalid_config" in r["responses"] for r in requests)
    physical_source = bool(serial_info and serial_info.get("source") == "physical_serial")
    return {
        "schema": "needlervx.board.bringup.v1",
        "source": "physical_serial" if physical_source else "unverified_input",
        "provenance": {"uart_events": provenance(events_path), "program_log": provenance(program_path)},
        "serial": {"info": serial_info, "rx_bytes": rx_bytes, "tx_bytes": tx_bytes,
                   "capture_closed": capture_closed, "capture_state": capture_state,
                   "ready_count": ready_count, "incomplete_line": line_buffer},
        "checks": {"program_success": program_success, "done_status_one": status_done_one,
                   "uart_boot_ready": bool(physical_source and boot_build and ready_count),
                   "probe_roundtrip": bool(physical_source and probe_success),
                   "model_command_roundtrip": bool(physical_source and model_requests),
                   "peripherals_physical_observation": False, "full_board_acceptance": False},
        "boot_build": boot_build, "requests": requests, "protocol_records": records,
        "coremark_lines": coremark_lines, "capture_errors": errors,
        "program_errors": [line for line in program.splitlines() if line.startswith("E:")],
        "limits": ["DONE confirms configuration; it does not prove CPU or model execution.",
                   "NR_RESULT and READY prove a protocol response, not physical LED/PWM waveforms.",
                   "CoreMark validity, ADC samples and model numeric agreement require separate checks.",
                   "Open capture hashes describe this snapshot and may change as data arrives."]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uart-events", required=True, type=Path)
    parser.add_argument("--program-log", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = summarize(args.uart_events, args.program_log)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["checks"]))


if __name__ == "__main__":
    main()
