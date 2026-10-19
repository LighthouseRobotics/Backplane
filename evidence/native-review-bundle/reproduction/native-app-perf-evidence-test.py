#!/usr/bin/env python3
"""Task-local artifact/summary controls; never execute a native app."""
import importlib.util
import json
import os
import pathlib
import socket
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('perf_evidence', ROOT / 'evidence/native-app-perf-evidence.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
checks = 0


def check(name, condition):
    global checks
    assert condition, name
    print('ok ' + name)
    checks += 1


baseline_script = module.git('ci-baseline', 'show', module.BASE + ':scripts/build-app.sh')
reviewed_script = module.git('combined-plan-only', 'show', 'f30b5a3d8619b71ae922ca2cea9618726091492f:scripts/build-app.sh')
check('exact baseline build script retains audited O3 flags', module.build_script_identity(baseline_script)['default_cflags'] == '-O3')
check('exact portable clock and lock script retains audited O3 flags', module.build_script_identity(reviewed_script)['default_cflags'] == '-O3')
for label, altered in [
    ('changed optimization', reviewed_script.replace(b'cflags=${BACKPLANE_CFLAGS:--O3}', b'cflags=${BACKPLANE_CFLAGS:--O0}')),
    ('later compiler flag override', reviewed_script + b'\nexport BP_CFLAGS=-O0\n'),
    ('unaudited script version', reviewed_script + b'\n# a different version\n'),
]:
    try:
        module.build_script_identity(altered)
    except ValueError:
        check(label + ' is refused by exact script identity', True)
    else:
        raise AssertionError(label + ' was accepted')


with tempfile.TemporaryDirectory(prefix='bp-native-perf-report-controls-') as temp:
    temp = pathlib.Path(temp)
    baseline = ROOT / 'artifacts/native-baseline'
    candidate = temp / 'synthetic-candidate'
    output = temp / 'results'
    candidate.mkdir()
    output.mkdir()
    # Candidate receipts are synthetic controls only. Its dummy ELF is never
    # executed, and no synthetic acceptance result is saved as real CI evidence.
    source = os.environ.get('BP_PERF_TEST_INPUT_COMMIT', '96f32a75b1290336686d491bf6b82e1c4cafa140')
    manifest = module.git('ci-acceptance', 'show', source + ':acceptance-inputs/20261019/manifest.json')
    scope = json.loads(manifest)['scopes']['native']
    (candidate / 'manifest.json').write_bytes(manifest)
    for filename in [scope['files'], scope['patch']]:
        (candidate / filename).write_bytes(module.git('ci-acceptance', 'show', source + ':acceptance-inputs/20261019/' + filename))
    binary = candidate / 'never-execute-this-test-ELF'
    binary.write_bytes(b'\x7fELFsynthetic-receipt-control-not-an-app')
    tools = (baseline / 'build/candidate-toolchain.txt').read_text()
    clang, _, remaining = tools.partition('\nbend ')
    (candidate / 'clang.log').write_text(clang + '\n')
    (candidate / 'toolchain.log').write_text('bend ' + remaining)
    identity = {'input_commit': source, 'checkout_commit': module.BASE,
                'applied_tree': scope['expected_tree'], 'patch_sha256': scope['patch_sha256']}
    receipt = {**identity, 'scope': 'native', 'result': 'pass', 'build_exit': 0, 'source_verified': identity,
               'artifacts': [{**identity, 'path': 'artifacts/dist/backplane', 'sha256': module.digest(binary), 'bytes': binary.stat().st_size},
                             {**identity, 'path': 'clang.log', 'sha256': module.digest(candidate / 'clang.log')}]}
    module.write(candidate / 'receipt.json', receipt)
    module.prepare(list(map(str, [baseline / 'dist/backplane', baseline, binary, candidate, output])))
    identities = json.loads((output / 'artifact-identities.json').read_text())
    check('actual downloaded baseline layout and immutable SHA receipt validate', identities['baseline']['binary_sha256'] == 'ff0a3b18b3e3f3ceac54d8b0ac84b62169c48a6042a141b5d935130dfa1c2c48')
    check('actual baseline compiler receipt is parsed by its real filename', identities['toolchain']['clang'].startswith('Ubuntu clang version 19.1.1'))
    check('snapshot label names CI input while product tree stays explicit', identities['candidate']['source_label'] == source and identities['candidate']['applied_tree'] == scope['expected_tree'])
    check('all measurements require the upgraded single fixture hash', identities['fixture_sha256'] == module.digest(ROOT / 'evidence/native-fixture-bots.jsonl'))

    for name in ['baseline-cold', 'candidate-cold', 'baseline-warm', 'candidate-warm']:
        (output / name).mkdir()
        module.write(output / name / 'status.json', {'status': 'PASS'})
    common = {'verdict': 'pass', 'baseline_binary_sha256': identities['baseline']['binary_sha256'],
              'candidate_binary_sha256': identities['candidate']['binary_sha256'],
              'baseline_source': identities['baseline']['source_label'], 'candidate_source': source,
              'fixture_sha256': module.FIXTURE, 'harness_sha256': module.digest(ROOT / 'native-glyph/test/tools/perf_load.ts')}
    input_report = {**common, 'input_targets': 12, 'title_targets': 0}
    title_report = {**common, 'input_targets': 0, 'title_targets': 21}

    def reset():
        for surface, value in [('input', input_report), ('title', title_report)]:
            module.write(output / f'compare-{surface}.json', value)
            (output / f'compare-{surface}.exit').write_text('0\n')
        for name in ['baseline-cold', 'candidate-cold', 'baseline-warm', 'candidate-warm']:
            module.write(output / name / 'status.json', {'status': 'PASS'})

    def rejected(name, change):
        reset()
        change()
        check(name, module.summary([str(output)])['result'] == 'incomplete_or_fail')

    reset()
    check('complete successful comparisons produce a pass summary', module.summary([str(output)])['result'] == 'pass')
    rejected('pass-looking output cannot hide nonzero comparison exit', lambda: (output / 'compare-input.exit').write_text('1\n'))
    rejected('file existence cannot hide a failed comparison verdict', lambda: module.write(output / 'compare-input.json', dict(input_report, verdict='fail')))
    rejected('malformed comparison JSON is refused', lambda: (output / 'compare-input.json').write_text('{broken'))
    rejected('missing comparison exit receipt is refused', lambda: (output / 'compare-title.exit').unlink())
    rejected('wrong comparison source label is refused', lambda: module.write(output / 'compare-input.json', dict(input_report, candidate_source='0' * 40)))
    rejected('wrong comparison binary hash is refused', lambda: module.write(output / 'compare-title.json', dict(title_report, baseline_binary_sha256='0' * 64)))
    rejected('incomplete target-map coverage is refused', lambda: module.write(output / 'compare-input.json', dict(input_report, input_targets=11)))
    rejected('baseline target failure stays a failure', lambda: module.write(output / 'baseline-cold/status.json', {'status': 'TARGET_FAIL'}))
    rejected('Status-tab null coverage cannot become a pass', lambda: module.write(output / 'candidate-cold/status.json', {'status': 'UNVERIFIED'}))
    rejected('malformed per-run status cannot become a pass', lambda: module.write(output / 'candidate-warm/status.json', []))
    rejected('missing raw comparison report is refused', lambda: (output / 'compare-title.json').unlink())
    rejected('nonnumeric comparison exit is refused', lambda: (output / 'compare-input.exit').write_text('unknown\n'))
with socket.socket() as listener:
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    listener.listen()
    try:
        module.port_check([str(port), ':54321'])
    except OSError:
        check('reusable port preflight still rejects an actual listener', True)
    else:
        raise AssertionError('live listener accepted')
    client = socket.create_connection(('127.0.0.1', port))
    accepted, _ = listener.accept()
    accepted.close()
    client.recv(1)
    client.close()
try:
    with socket.socket() as bare:
        bare.bind(('127.0.0.1', port))
except OSError:
    check('bare-bind negative control reproduces TIME_WAIT false refusal', True)
else:
    raise AssertionError('expected owned local TIME_WAIT for this Linux regression')
module.port_check([str(port), ':54321'])
check('preflight accepts normal reuse after the owned listener exits', True)
print(f'{checks} artifact-layout/summary/port controls passed; no native app executed')
