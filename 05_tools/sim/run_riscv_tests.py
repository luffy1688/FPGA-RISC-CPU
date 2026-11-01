#!/usr/bin/env python3
"""Compile unchanged upstream RV32UI/UM bodies and execute the project's RTL.

Stable output directories are overwritten on each invocation. The local header
adapts reset/trap/termination only. No architecture certification is implied.
"""
import argparse
import datetime
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PREFIX = '/opt/Andestech/toolchains/nds32le-elf-mculib-v5/bin/riscv32-unknown-elf-'
RESULT = re.compile(r'NR_RISCV_RESULT status=(\w+) code=([0-9a-f]+) cycles=(\d+) pc=([0-9a-f]+) testnum=(\d+) waits=(\d+) failure_branch_pc=([0-9a-f]+) trap_pc=([0-9a-f]+)')

def capture(args, log=None, timeout=60):
    result = subprocess.run([str(x) for x in args], cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    if log is not None:
        Path(log).write_text(result.stdout, encoding='utf-8')
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', default=DEFAULT_PREFIX)
    parser.add_argument('--out',type=Path,help='Isolated result directory; default preserves historical behavior')
    parser.add_argument('--waits', type=int, choices=[0, 1], default=1)
    parser.add_argument('--tests', nargs='*', help='optional stems, e.g. rv32ui-add rv32um-div')
    args = parser.parse_args()
    source = ROOT / '09_refs/riscv-tests'
    out = args.out if args.out else ROOT / '07_runs/riscv_tests'
    if not out.is_absolute():out=ROOT/out
    if args.tests and not args.out:
        out = out / 'selected' # Keep focused reruns from replacing the full-suite evidence.
    out.mkdir(parents=True, exist_ok=True)
    if not (source / 'isa/rv32ui/add.S').exists():
        sys.exit('Missing 09_refs/riscv-tests; clone https://github.com/riscv-software-src/riscv-tests.git there first.')
    tests = [(group, file) for group in ('rv32ui', 'rv32um')
             for file in sorted((source / 'isa' / group).glob('*.S'))
             if file.stem != 'ma_data']
    if args.tests:
        tests = [(g, f) for g, f in tests if f'{g}-{f.stem}' in args.tests]
        if len(tests) != len(set(args.tests)):
            sys.exit('Unknown or excluded --tests selection')
    tests += [('harness', ROOT / '03_sw/riscv_tests/diagnostic_fail.S'),
              ('harness', ROOT / '03_sw/riscv_tests/diagnostic_trap.S')]
    simulator = out / 'riscv_tests.vvp'
    compile_result = capture(['iverilog', '-g2012', '-s', 'tb_riscv_tests', '-o', simulator,
                             *sorted((ROOT / '01_rtl/cpu').glob('*.sv')),
                             ROOT / '02_tb/system/tb_riscv_tests.sv'], out / 'rtl_compile.log')
    if compile_result.returncode:
        sys.exit('RTL compile failed; see 07_runs/riscv_tests/rtl_compile.log')
    results = []
    for group, file in tests:
        name = f'{group}-{file.stem}'
        build = out / name
        build.mkdir(exist_ok=True)
        elf, binary, memory = (build / ('test.' + ext) for ext in ('elf', 'bin', 'hex'))
        gcc = capture([args.prefix + 'gcc', '-march=rv32im_zicsr_zifencei', '-mabi=ilp32',
                       '-nostdlib', '-nostartfiles', '-mno-relax',
                       '-I', ROOT / '03_sw/riscv_tests', '-I', source / 'isa/macros/scalar',
                       '-T', ROOT / '03_sw/riscv_tests/linker.ld', file, '-o', elf], build / 'build.log')
        record = {'name': name, 'group': group, 'source': str(file.relative_to(ROOT))}
        if gcc.returncode:
            record.update(status='BUILD_FAIL', failure='build.log')
        else:
            obj = capture([args.prefix + 'objcopy', '-O', 'binary', elf, binary])
            if obj.returncode:
                sys.exit(f'objcopy failed: {name}')
            raw = binary.read_bytes()
            raw += b'\0' * ((-len(raw)) % 4)
            memory.write_text(''.join(f'{int.from_bytes(raw[i:i+4], "little"):08x}\n'
                                     for i in range(0, len(raw), 4)))
            syms = capture([args.prefix + 'nm', elf]).stdout
            record['static_assertion_labels'] = len(re.findall(r'\btest_\d+$', syms, re.M))
            fail_match = re.search(r'^([0-9a-f]+)\s+\w\s+fail$', syms, re.M)
            fail_pc = fail_match.group(1) if fail_match else 'ffffffff'
            try:
                run = capture(['vvp', simulator, '+mem=' + str(memory), '+waits=' + str(args.waits),
                               '+words=' + str(len(raw)//4), '+fail_pc=' + fail_pc],
                              build / 'run.log', timeout=45)
                match = RESULT.search(run.stdout)
                if match:
                    status, code, cycles, pc, testnum, waits, failure_pc, trap_pc = match.groups()
                    record.update(status=status, code='0x' + code, cycles=int(cycles),
                                  last_commit_pc='0x' + pc, last_testnum=int(testnum), waits=int(waits),
                                  failure_branch_pc='0x' + failure_pc, trap_pc='0x' + trap_pc)
                    if group == 'harness':
                        expected_code = '0x00000055' if file.stem == 'diagnostic_fail' else '0x80000002'
                        label = 'assertion_branch' if file.stem == 'diagnostic_fail' else 'trap_instruction'
                        address = re.search(r'^([0-9a-f]+)\s+\w\s+' + label + r'$', syms, re.M)
                        observed_pc = record['failure_branch_pc'] if file.stem == 'diagnostic_fail' else record['trap_pc']
                        record['observed_status'] = status
                        record['expected_code'] = expected_code
                        record['expected_pc'] = '0x' + address.group(1) if address else None
                        record['status'] = 'PASS' if (status == 'FAIL' and record['code'] == expected_code and
                                                     observed_pc == record['expected_pc']) else 'FAIL'
                    if run.returncode and status == 'PASS':
                        record['status'] = 'SIM_FAIL'
                else:
                    record.update(status='SIM_FAIL', failure='No machine-readable result; inspect run.log')
            except subprocess.TimeoutExpired as error:
                (build / 'run.log').write_text((error.stdout or b'').decode(errors='replace'))
                record.update(status='HOST_TIMEOUT')
        results.append(record)
        print(name + ': ' + record['status'], flush=True)
    diagnostics = [r for r in results if r['group'] == 'harness']
    results = [r for r in results if r['group'] != 'harness']
    commit = capture(['git', '-C', source, 'rev-parse', 'HEAD']).stdout.strip()
    report = {
        'schema_version': 1,
        'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'target': 'rv32i_core RTL, 256 KiB shared RAM, no caches; not physical FPGA',
        'upstream': {'url': 'https://github.com/riscv-software-src/riscv-tests', 'commit': commit,
                     'license': 'BSD-style UC Regents (see 09_refs/riscv-tests/LICENSE)'},
        'adapter': '03_sw/riscv_tests/riscv_test.h; original test bodies and test_macros.h unchanged',
        'toolchain': capture([args.prefix + 'gcc', '--version']).stdout.splitlines()[0],
        'wait_states': bool(args.waits), 'total': len(results),
        'passed': sum(r['status'] == 'PASS' for r in results),
        'failed': sum(r['status'] != 'PASS' for r in results),
        'excluded': [{'name': 'rv32ui-ma_data', 'reason': 'Upstream test requires successful misaligned load/store; project intentionally traps misaligned accesses and tests that policy in cpu_acceptance.'}],
        'limits': ['Adapted upstream instruction regression, not riscv-arch-test certification.',
                   'No privileged/atomic/floating-point/vector tests.',
                   'No cache, PDS, post-route timing, or physical board coverage.',
                   'Static assertion labels describe source labels; they are not runtime coverage counters.'],
        'harness_diagnostics': diagnostics,
        'harness_diagnostics_passed': all(r['status']=='PASS' for r in diagnostics),
        'results': results,
    }
    report['groups'] = {g: {'passed': sum(r['status']=='PASS' for r in results if r['group']==g),
                              'total': sum(r['group']==g for r in results)}
                        for g in ('rv32ui', 'rv32um')}
    (out / 'current_report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    lines = ['# RV32IM 上游指令自检摘要', '',
             f"- 结果：{report['passed']}/{report['total']} 通过，失败 {report['failed']}。",
             f'- 对象：真实 CPU RTL，256 KiB 共享 RAM；确定性总线等待={bool(args.waits)}（默认取指每三周期、数据每四周期等待）。',
             '- 来源：未改动的官方 riscv-tests RV32UI/RV32UM 指令测试主体；自定义裸机复位、陷阱及 pass/fail 输出适配。',
             '- 额外 2 个刻意失败诊断已验证：软件断言可记录失败编号/分支 PC，非法指令可记录 mcause/mepc；不计入上游测试总数。',
             '- 这不是正式架构认证，也没有覆盖 Cache/PDS/实体 FPGA。',
             '- ma_data 排除：CPU 对未对齐访问采用陷阱策略，已有 cpu_acceptance 专门验收该策略。',
             f'- 上游提交：{commit}', '',
             '| 程序 | 结果 | 周期 | 最后提交 PC | 最后测试编号 |', '|---|---|---:|---|---:|']
    for r in results:
        lines.append(f"| {r['name']} | {r['status']} | {r.get('cycles', '')} | {r.get('last_commit_pc', '')} | {r.get('last_testnum', '')} |")
    (out / 'current_report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"SUMMARY {report['passed']}/{report['total']} PASS; {report['failed']} FAIL")
    return 1 if report['failed'] or not report['harness_diagnostics_passed'] else 0

if __name__ == '__main__':
    sys.exit(main())
