#!/usr/bin/env python3
"""Publish a small reproducible handoff from canonical server sources.
No credentials, licences, candidate training outputs or large simulator builds.
Stable output paths are overwritten rather than creating version directories.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python 3.8 on the shared server
    ZoneInfo = None
import json,tarfile,zipfile
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'08_release'
OUT.mkdir(exist_ok=True)

# PDS keeps large intermediate databases beside its project inputs.  Package
# only inputs and the explicitly selected small evidence reports below.
EXCLUDED_DIRS = {
    '__pycache__', 'build', '.git', 'vendor_ref', 'node_modules',
    'compile', 'synthesize', 'device_map', 'place_route', 'report_timing',
    'report_power', 'generate_bitstream', 'generate_netlist', 'constraint_check',
    'logbackup', 'bak', 'license', 'licenses', 'credentials', 'secrets', 'downloads',
}
EXCLUDED_SUFFIXES = {
    '.bak', '.db', '.adf', '.vm', '.vcd', '.fst', '.pyc', '.o', '.vvp', '.so',
    '.lic', '.pem', '.key', '.sbit', '.smsk', '.snr', '.rtr', '.prr',
    '.gguf', '.safetensors', '.onnx', '.ckpt', '.pth', '.h5',
    '.zip', '.gz', '.bz2', '.xz', '.7z', '.rar', '.exe', '.dll',
}

def excluded_path(path):
    """Shared exclusions apply to source and explicit handoff lists."""
    parts = path.relative_to(ROOT).parts
    return (any(part.lower() in EXCLUDED_DIRS for part in parts) or
            path.suffix.lower() in EXCLUDED_SUFFIXES or
            path.name.lower().endswith(('.bak', '~')) or
            path.name.lower().startswith('.env') or
            path.name.lower() in {'known_hosts', 'id_rsa', 'id_ed25519'} or
            'credential' in path.name.lower())

def source_input(path):
    if not path.is_file() or excluded_path(path):
        return False
    if path.suffix.lower() in {'.elf', '.bin'}:
        return False
    if path.suffix.lower() == '.pt' and path.name != 'initialization.pt':
        return False
    if path.name in {'model_demo', 'host_acceptance'}:
        return False
    # PDS folders include run logs/reports at their root as well as databases.
    # A whitelist avoids silently packaging a new generated file type later.
    if path.relative_to(ROOT).parts[0].startswith('06_pango'):
        # impl.tcl and helper .pds files are PDS-generated flow transcripts,
        # not the source-bearing project or our post-route input scripts.
        if path.name in {'impl.tcl', 'pangu_200pro_board_timing.pds', 'pangu_200pro_board_export.pds'}:
            return False
        return path.suffix.lower() in {'.md', '.pds', '.fdc', '.sdc', '.tcl', '.f', '.mem'} or path.name == 'Makefile'
    return True

# Keep path hierarchy because PDS and Makefiles use relative source paths.
board=list((ROOT/'01_rtl').rglob('*.sv'))
for name in ['BOARD.md','BOARD_HANDOFF.md','TEMPERATURE.md','rtl.f','pangu_200pro_board.pds','pangu_200pro_board.fdc']:
    board.append(ROOT/'06_pango'/name)
board.extend((ROOT/'06_pango/firmware').glob('*.mem'))
board.extend(p for p in (ROOT/'05_tools/console').glob('*') if p.is_file())
board.extend([ROOT/'09_refs/coremark/LICENSE.md',ROOT/'09_refs/needle/LICENSE',ROOT/'09_refs/riscv-tests/LICENSE'])
evidence={
 'model':['current_report.json','current_uart_report.json','current_irq_report.json','runtime_pmu_report.json',
          'confidence_gate_report.json','host_acceptance.log','interactive.log','selftest.log','irq.log','interactive.elf','interactive.bin'],
 'coremark':['current_report.json','cache_perf.json','performance.log','validation.log'],
 'sim':['board_smoke.log','cache_bank.log','temperature.log','hmic_bridge.log','word_bus_cdc.log'],
 'pds':['current_report.json'],
 'riscv_tests':['current_report.json','current_report.md','current_run.log'],
 'eval':['current_independent_report.json','current_independent_report.md','current_independent_results.jsonl','frozen_semantic_baseline.json','current_generalization_report.json','current_generalization_report.md','generalization_fresh_predictions.jsonl'],
 'release':['current_evidence_report.md'],
 'ddr':['integration_report.json','integration_report.md','firmware_build.log','tb_needle_ddr_bringup.log','tb_needle_ddr_fault.log','bringup.mem','fault.mem'],
 'model/optimization':['current_report.json','current_report.md','profile_report.json']}
for group,names in evidence.items():board.extend(ROOT/'07_runs'/group/n for n in names)
# Source needed for reproducible standard CPU tests (all referenced includes).
refs=[]
for name in ['rv32ui','rv32um','rv64ui','rv64um']:
    refs.extend((ROOT/'09_refs/riscv-tests/isa'/name).glob('*.S'))
refs += [ROOT/'09_refs/riscv-tests/isa/macros/scalar/test_macros.h',ROOT/'09_refs/riscv-tests/LICENSE']
source=[]
for folder in ['00_docs','01_rtl','02_tb','03_sw','04_model','05_tools','06_pango']:
    for p in (ROOT/folder).rglob('*'):
        if not source_input(p):continue
        source.append(p)
source += board+refs+[ROOT/'README.md',ROOT/'STATUS.md']
source += list((ROOT/'09_refs/coremark').glob('*.c'))
source += [ROOT/'09_refs/coremark/coremark.h',ROOT/'09_refs/coremark/README.md']
# Local handoff contains reproducible inputs, not PDS working databases.
local=sorted(p for p in set(source) if p.is_file() and not excluded_path(p))
with tarfile.open(OUT/'local_export.tar.gz','w:gz') as tar:
    for p in local:tar.add(p,arcname='上板交付/工程/'+p.relative_to(ROOT).as_posix(),recursive=False)
    tar.add(ROOT/'STATUS.md',arcname='FPGA_当前开发进度.md',recursive=False)
with zipfile.ZipFile(OUT/'NeedleRV-X_源码与结果.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in local:
        if p.suffix in ['.elf','.bin']:continue
        z.write(p,'NeedleRV-X/'+p.relative_to(ROOT).as_posix())
full_bitstream=ROOT/'06_pango/generate_bitstream/pangu_200pro_board.sbit'
smoke_bitstream=ROOT/'06_pango_smoke/generate_bitstream/pangu_200pro_smoke.sbit'
full_ready=full_bitstream.is_file() and full_bitstream.stat().st_size>0
smoke_ready=smoke_bitstream.is_file() and smoke_bitstream.stat().st_size>0
report_now = (datetime.now(ZoneInfo('Asia/Hong_Kong')) if ZoneInfo else
              datetime.now(timezone.utc) + timedelta(hours=8))
manifest={'date':report_now.date().isoformat(),
 'kind':'source_and_selected_evidence','model_stage':'stage3_generalization',
 'no_bitstream':not full_ready,'no_full_bitstream':not full_ready,'source_root':str(ROOT),
 'full_bitstream':{'exists':full_ready,'path':full_bitstream.relative_to(ROOT).as_posix(),
                   'packaged':False,'boundary':'File existence does not establish physical-board validation'},
 'smoke_bitstream':{'exists':smoke_ready,'path':smoke_bitstream.relative_to(ROOT).as_posix(),
                    'packaged':False,'purpose':'First UART/LED bring-up only; not the full AI/XND image'},
 'physical_top':'pangu_200pro_board','firmware':'06_pango/firmware/model_interactive.mem',
 'adc':'GTP_ADC_E2 candidate, hardware not yet tested','memory':'256KiB BRAM default; optional DDR behavior path integrated; PHY/real bandwidth pending',
 'runtime_config':'control :config 0..6; NR_CONFIG confirms actual state',
 'software_evidence':'07_runs/release/current_evidence_report.md',
 'pds_evidence':'07_runs/pds/current_report.json',
 'needs':([] if full_ready else ['full PDS timing/bitstream'])+['physical board evidence','final contest submission template'],
 'boundary':'Firmware .mem is RAM initialization, not a JTAG .sbit; test results are RTL/host, not board'}
model_report=json.loads((ROOT/'07_runs/model/current_report.json').read_text(encoding='utf-8'))
manifest['kernel_stage']=model_report.get('kernel_stage')
manifest['kernel_options']=model_report.get('kernel_options')
(OUT/'release_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for name in ['local_export.tar.gz','NeedleRV-X_源码与结果.zip']:
    print(name,(OUT/name).stat().st_size,'bytes')
