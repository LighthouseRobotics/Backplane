#!/usr/bin/env python3
"""Validate downloaded native artifact provenance and preserve perf verdicts."""
import hashlib
import json
import os
import pathlib
import re
import socket
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = '30884966ef59c383581bcd1b7653f8f739cf009e'
FLAGS = 'LLVM=19;CFLAGS=-O3;LOW_MEM=1;JOBS=2;GOOGLE_BAKE=0'
FIXTURE = 'ac5f4374d7946569b420d7b2ca2d5890c99d54d323a819a6d66beaf2d824b543'
FIXTURE_NAME = 'native-fixture-bots.jsonl'
BUILD_SCRIPTS = {
    '27c35f277dbd4fbd38cc10f50d5bd0aa2978e62320d4115e4d3de1dc63846a64':
        'upstream baseline build script',
    '7b47111aad198e5ecc7f5b5e350ef3d30892643aa4e3431ca47e0370055c7c42':
        'f30b5a3d reviewed lock detection and portable clock/RSS changes; compiler flags unchanged',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with pathlib.Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(ROOT / repo), *args])


def fullsha(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{40}', value), 'full 40-character source label required')
    return value


def write(path, value):
    pathlib.Path(path).write_text(json.dumps(value, indent=2) + '\n')


def toolchain(text):
    clang = re.search(r'(?m)^.*clang version 19\.[^\n]+', text)
    bend = re.search(r'(?m)^bend (\d+\.\d+\.\d+)', text)
    bun = re.search(r'(?m)^(\d+\.\d+\.\d+)\s*$', text)
    require(clang and bend and bun, 'missing LLVM 19/Bend/Bun toolchain receipt')
    return {'clang': clang[0], 'bend': bend[1], 'bun': bun[1]}


def workflow_flags(text):
    for key, expected in [('BACKPLANE_LOW_MEM', '1'), ('BACKPLANE_JOBS', '2'), ('BACKPLANE_GOOGLE_BAKE', '0')]:
        require(re.search(rf'{key}:\s*[\"\']{expected}[\"\']', text), f'CI workflow lacks {key}={expected}')


def build_script_identity(script):
    sha = hashlib.sha256(script).hexdigest()
    require(sha in BUILD_SCRIPTS, 'candidate build script is not an exact audited version')
    require(script.count(b'cflags=${BACKPLANE_CFLAGS:--O3}') == 1,
            'audited build script does not retain the -O3 default')
    return {'sha256': sha, 'audit': BUILD_SCRIPTS[sha], 'default_cflags': '-O3'}


def prepare(args):
    baseline_bin, baseline_root, candidate_bin, candidate_root, out = map(pathlib.Path, args)
    out.mkdir(parents=True, exist_ok=True)
    for binary in [baseline_bin, candidate_bin]:
        with binary.open('rb') as stream:
            require(stream.read(4) == b'\x7fELF', f'not a downloaded Linux ELF: {binary}')
    raw_source = baseline_root / 'build/candidate-source.txt'
    source_lines = raw_source.read_text().splitlines()
    baseline_source = fullsha(source_lines[0])
    require(not any(line.strip() for line in source_lines[1:]), 'baseline artifact was built from a dirty checkout')
    changed = git('ci-baseline', 'diff', '--name-only', BASE, baseline_source).decode().splitlines()
    require(changed == ['.github/workflows/contribution-candidate.yml'], 'baseline contains product changes beyond its temporary workflow')
    baseline_workflow = git('ci-baseline', 'show', baseline_source + ':.github/workflows/contribution-candidate.yml').decode()
    workflow_flags(baseline_workflow)
    app_script = git('ci-baseline', 'show', BASE + ':scripts/build-app.sh')
    require(b'cflags=${BACKPLANE_CFLAGS:--O3}' in app_script, 'baseline default optimization differs')
    sums = (baseline_root / 'build/candidate-artifacts.sha256').read_text().splitlines()
    expected = [line.split()[0] for line in sums if len(line.split()) == 2 and line.split()[1] == 'dist/backplane']
    require(expected == [digest(baseline_bin)], 'baseline binary differs from downloaded SHA-256 receipt')
    baseline_tools = toolchain((baseline_root / 'build/candidate-toolchain.txt').read_text())

    receipt = json.loads((candidate_root / 'receipt.json').read_text())
    candidate_source = fullsha(receipt.get('input_commit'))
    require(receipt.get('scope') == 'native' and receipt.get('checkout_commit') == BASE, 'candidate receipt is not the requested native snapshot/base')
    require(receipt.get('result') == 'pass' and receipt.get('build_exit') == 0, 'candidate proof/build receipt did not pass')
    manifest_bytes = git('ci-acceptance', 'show', candidate_source + ':acceptance-inputs/20261019/manifest.json')
    manifest = json.loads(manifest_bytes)
    scope = manifest['scopes']['native']
    require((candidate_root / 'manifest.json').read_bytes() == manifest_bytes, 'downloaded manifest differs from immutable CI input commit')
    require(receipt.get('applied_tree') == scope['expected_tree'] and receipt.get('patch_sha256') == scope['patch_sha256'], 'candidate applied tree/patch differs from frozen input')
    verified = receipt.get('source_verified') or {}
    for key in ['input_commit', 'checkout_commit', 'applied_tree', 'patch_sha256']:
        require(verified.get(key) == receipt.get(key), f'candidate source verification differs: {key}')
    file_table = candidate_root / scope['files']
    require(digest(file_table) == scope['files_sha256'], 'candidate full file-table hash mismatch')
    require(digest(candidate_root / scope['patch']) == scope['patch_sha256'], 'candidate patch hash mismatch')
    table = {item['path']: item for item in json.loads(file_table.read_text())}
    product_name = scope.get('source_worktree')
    require(isinstance(product_name, str) and re.fullmatch('[a-z0-9-]+', product_name), 'invalid immutable product worktree name')
    product_root = (ROOT / product_name).resolve()
    require(product_root.parent == ROOT.resolve() and product_root.is_dir(), 'product worktree is not an isolated task checkout')
    candidate_script = (product_root / 'scripts/build-app.sh').read_bytes()
    require(table['scripts/build-app.sh']['sha256'] == hashlib.sha256(candidate_script).hexdigest(),
            'candidate build script differs from immutable source table')
    baseline_build_script = build_script_identity(app_script)
    candidate_build_script = build_script_identity(candidate_script)
    # App bytes stay pinned to CI. Measurement-only repairs may be committed
    # afterward, but must have their own immutable source identity and both
    # experiments must use those exact committed bytes.
    measurement_commit = fullsha(os.environ.get('BP_PERF_HARNESS_COMMIT') or git('native-glyph', 'rev-parse', 'HEAD').decode().strip())
    measurement_files = {}
    for relative in ['test/tools/' + name for name in ['perf_load.ts', 'native_display.ts', 'perf_guard.ts', 'xpoke.c', 'native_display_compare.ts', 'perf_standin.ts']] + ['src/core/cbor.bend']:
        expected = hashlib.sha256(git('native-glyph', 'show', measurement_commit + ':' + relative)).hexdigest()
        require(digest(ROOT / 'native-glyph' / relative) == expected, 'measurement bytes differ from declared committed harness: ' + relative)
        require((ROOT / 'native-glyph' / relative).read_bytes() == (ROOT / 'native-baseline' / relative).read_bytes(), 'baseline/candidate driver bytes differ: ' + relative)
        measurement_files[relative] = expected
    for relative, item in table.items():
        if relative.endswith('.bend') or relative.startswith('src/'):
            require(digest(product_root / relative) == item['sha256'], 'product bytes changed after the app snapshot: ' + relative)
    artifact = [entry for entry in receipt.get('artifacts', []) if entry.get('path') == 'artifacts/dist/backplane']
    require(len(artifact) == 1 and artifact[0].get('sha256') == digest(candidate_bin) and artifact[0].get('bytes') == candidate_bin.stat().st_size, 'candidate binary differs from CI artifact receipt')
    for key in ['input_commit', 'checkout_commit', 'applied_tree', 'patch_sha256']:
        require(artifact[0].get(key) == receipt.get(key), 'candidate artifact identity mismatch: ' + key)
    clang_entry = [entry for entry in receipt['artifacts'] if entry.get('path') == 'clang.log']
    require(len(clang_entry) == 1 and clang_entry[0]['sha256'] == digest(candidate_root / 'clang.log'), 'candidate compiler receipt hash mismatch')
    candidate_tools = toolchain((candidate_root / 'clang.log').read_text() + '\n' + (candidate_root / 'toolchain.log').read_text())
    require(candidate_tools == baseline_tools, 'baseline/candidate recorded compiler or runtime versions differ')
    candidate_workflow = git('ci-acceptance', 'show', candidate_source + ':.github/workflows/acceptance-inputs-20261019.yml').decode()
    workflow_flags(candidate_workflow)
    require(digest(ROOT / 'evidence' / FIXTURE_NAME) == FIXTURE, 'synthetic fixture hash mismatch')
    identities = {
        'schema': 1, 'build_flags': FLAGS, 'fixture_sha256': FIXTURE, 'toolchain': baseline_tools,
        'build_scripts': {'baseline': baseline_build_script, 'candidate': candidate_build_script},
        'measurement_harness': {'commit': measurement_commit, 'files': measurement_files,
                                'scope': 'Separately committed measurement code. App source and binary identities remain pinned to their original CI receipts.'},
        'baseline': {'source_label': baseline_source, 'identity_kind': 'committed-ci-build', 'product_base': BASE,
                     'binary_sha256': digest(baseline_bin), 'artifact_root': str(baseline_root),
                     'source_receipt_sha256': digest(raw_source), 'hash_receipt_sha256': digest(baseline_root / 'build/candidate-artifacts.sha256')},
        'candidate': {'source_label': candidate_source, 'identity_kind': 'ci-applied-snapshot',
                      'checkout_commit': BASE, 'applied_tree': scope['expected_tree'], 'patch_sha256': scope['patch_sha256'],
                      'source_head_before_patch': scope['source_head'], 'product_worktree': product_name, 'binary_sha256': digest(candidate_bin),
                      'artifact_root': str(candidate_root), 'receipt_sha256': digest(candidate_root / 'receipt.json')},
        'source_label_note': 'Candidate --source-sha labels the immutable CI input commit containing the applied patch. Product identity is checkout_commit + applied_tree + patch_sha256; the uncommitted candidate is not claimed to be product HEAD.'}
    write(out / 'artifact-identities.json', identities)
    for label, value in [('baseline', baseline_source), ('candidate', candidate_source)]:
        (out / (label + '.source-label')).write_text(value + '\n')


def port_check(args):
    port, display = int(args[0]), args[1]
    require(re.fullmatch(r':[0-9]+', display), 'invalid dedicated display')
    number = display[1:]
    require(not pathlib.Path('/tmp/.X11-unix/X' + number).exists() and not pathlib.Path('/tmp/.X' + number + '-lock').exists(), 'dedicated X display is already owned; refusing to share/remove it')
    with socket.socket() as sock:
        # Fresh runs reuse their owned port after a previous server exits.
        # TIME_WAIT is not a listener; SO_REUSEADDR permits that normal reuse
        # while an existing listener still prevents this bind.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1', port))


def report(args):
    path, identities_path, side, mode, rc_text = args
    output = pathlib.Path(path).parent
    try:
        data = json.loads(pathlib.Path(path).read_text())
        identities = json.loads(pathlib.Path(identities_path).read_text())
        expected_phases = {'idle', 'bg', 'fg', 'type', 'input-display', 'open', 'normal'} if mode == 'cold' else {'open'}
        require({p['name'] for p in data['phases']} == expected_phases and len(data['phases']) == len(expected_phases), 'required phases missing or duplicated')
        require(data['binary_sha256'] == identities[side]['binary_sha256'] and data['source_sha_declared'] == identities[side]['source_label'], 'measured artifact/source differs from receipt')
        require(data['build_flags_declared'] == FLAGS and data['agents'] == 10 and data['secs'] == 5, 'measured build/workload labels differ')
        require(data['log_sha256'] == FIXTURE, 'measured fixture differs')
        for key, name in [('harness_sha256', 'perf_load.ts'), ('observer_sha256', 'native_display.ts')]:
            require(data[key] == digest(ROOT / 'native-glyph/test/tools' / name), 'measured driver/observer differs')
        require(data['native_display']['inputs_enabled'] == (mode == 'cold') and data['native_display']['opens_enabled'] == (mode == 'warm'), 'measurement cache/surface mode differs')
        failed, unverified = [], []
        for phase in data['phases']:
            require(phase.get('checks'), 'phase verdicts missing')
            for name, value in phase['checks'].items():
                require(value is True or value is False or value is None, 'invalid target verdict')
                if value is False:
                    failed.append({'phase': phase['name'], 'check': name})
                elif value is None:
                    unverified.append({'phase': phase['name'], 'check': name})
        require(data.get('bot_streaming') is True and data.get('stray_agents') == [], 'stand-in workload or process-isolation guard failed')
        require(int(rc_text) == 0, 'driver exited nonzero; execution/workload is incomplete')
        status = 'TARGET_FAIL' if failed else 'UNVERIFIED' if unverified else 'PASS'
        result = {'status': status, 'execution_exit': int(rc_text), 'failed_checks': failed, 'unverified_checks': unverified}
        # TMPDIR is scoped beneath this run, including all raw traces and homes.
        home = pathlib.Path(data['home']).resolve()
        require(home.is_relative_to(output.resolve() / 'tmp'), 'raw trace home escapes the owned run directory')
        root = home.parent
        require((root / 'trace.json').is_file(), 'raw native trace missing')
        result['raw_root'] = str(root)
        result['trace_sha256'] = digest(root / 'trace.json')
        result['demands_log'] = str(root / 'display-demands.jsonl')
        require(pathlib.Path(result['demands_log']).is_file(), 'independent demand journal missing')
    except (OSError, ValueError, KeyError, TypeError) as error:
        result = {'status': 'EXECUTION_FAIL', 'execution_exit': int(rc_text), 'error': str(error)}
    write(output / 'status.json', result)
    print(result['status'])


def summary(args):
    out = pathlib.Path(args[0])
    identities = json.loads((out / 'artifact-identities.json').read_text())
    runs = {}
    for name in ['baseline-cold', 'candidate-cold', 'baseline-warm', 'candidate-warm']:
        try:
            runs[name] = json.loads((out / name / 'status.json').read_text())
            require(isinstance(runs[name], dict) and runs[name].get('status') in ['PASS', 'TARGET_FAIL', 'UNVERIFIED', 'EXECUTION_FAIL'], 'invalid per-run status')
        except (OSError, ValueError) as error:
            runs[name] = {'status': 'EXECUTION_FAIL', 'error': str(error)}
    comparisons = {}
    for surface, expected_counts in [('input', (12, 0)), ('title', (0, 21))]:
        try:
            code = int((out / f'compare-{surface}.exit').read_text().strip())
            require(code == 0, f'comparison exited {code}')
            value = json.loads((out / f'compare-{surface}.json').read_text())
            require(value.get('verdict') == 'pass', 'comparison did not return a pass verdict')
            expected = {'baseline_binary_sha256': identities['baseline']['binary_sha256'],
                        'candidate_binary_sha256': identities['candidate']['binary_sha256'],
                        'baseline_source': identities['baseline']['source_label'],
                        'candidate_source': identities['candidate']['source_label'],
                        'fixture_sha256': FIXTURE,
                        'harness_sha256': digest(ROOT / 'native-glyph/test/tools/perf_load.ts')}
            for key, wanted in expected.items():
                require(value.get(key) == wanted, 'comparison identity differs: ' + key)
            require((value.get('input_targets'), value.get('title_targets')) == expected_counts, 'comparison target coverage differs')
            comparisons[surface] = {'status': 'PASS', 'exit': code, 'report_sha256': digest(out / f'compare-{surface}.json')}
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            comparisons[surface] = {'status': 'FAIL', 'error': str(error)}
    passed = all(value.get('status') == 'PASS' for value in runs.values()) and all(value['status'] == 'PASS' for value in comparisons.values())
    result = {'result': 'pass' if passed else 'incomplete_or_fail', 'runs': runs,
              'independent_reference_comparisons': comparisons,
              'limits': {'frame_p99_ms': 8, 'streaming_or_input_ms': 16, 'open_ms': 50, 'agent_line_p99_ms': 2},
              'scope': 'X-server composer/title content and trace processing. Status tab, full timeline and physical scanout are not certified. Configured secs=5 applies to timed phases; typing/open/normal use fixed event workloads.'}
    write(out / 'summary.json', result)
    return result


if __name__ == '__main__':
    operation, *arguments = sys.argv[1:]
    if operation == 'summary':
        result = summary(arguments)
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result['result'] == 'pass' else 1)
    {'prepare': prepare, 'ports': port_check, 'report': report}[operation](arguments)
