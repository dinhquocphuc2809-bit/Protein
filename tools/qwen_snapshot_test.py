"""Bounded deployed-app cold restore test, including retirement and system logs."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import wave

from operate_modal import environment

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--control', action='store_true')
    parser.add_argument('--cycles', type=int, choices=range(1, 7), default=4)
    args = parser.parse_args()
    name = 'vocalm-qwen-cold-control' if args.control else 'vocalm-qwen-snapshot-test'
    folder = ROOT/'.private/asr-snapshot'
    folder.mkdir(exist_ok=True)
    with wave.open(str(ROOT/'.private/asr-second-video/video.wav')) as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 16000):
            raise ValueError('Benchmark requires mono PCM16 audio at 16 kHz')
        frames = source.readframes(28*16000)
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as output:
        output.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        output.writeframes(frames)
    audio = buffer.getvalue()
    (folder/'warmup.wav').write_bytes(audio)
    env = environment(1)
    env.update(VOCALM_SNAPSHOT_TEST='0' if args.control else '1', PYTHONPATH=str(ROOT))
    os.environ.update(env)
    import modal
    def cli(*parts, timeout=60):
        return subprocess.run([sys.executable, '-m', 'modal', *parts], env=env, cwd=ROOT,
                              capture_output=True, timeout=timeout, encoding='utf-8')
    report = {'at': datetime.now(timezone.utc).isoformat(), 'app': name, 'snapshot': not args.control,
              'audio_sha256': hashlib.sha256(audio).hexdigest(), 'cycles': [], 'production_changed': False}
    path = ROOT/'research/benchmarks'/f'{name}.json'
    def save():
        path.write_text(json.dumps(report, indent=2)+'\n')
    app_id = None
    try:
        deployed = cli('deploy', 'gpu/asr_snapshot_probe.py', timeout=180)
        (folder/(name+'-deploy.log')).write_text(deployed.stdout+deployed.stderr, encoding='utf-8')
        if deployed.returncode:
            raise RuntimeError('Deployment failed; inspect private log')
        apps = json.loads(cli('app', 'list', '--json').stdout)
        app_id = next(a['app_id'] for a in apps if a['description'] == name and a['state'] == 'deployed')
        report['app_id'] = app_id
        worker = modal.Cls.from_name(name, 'Probe')()
        for index in range(args.cycles):
            if index:
                deadline = time.monotonic()+180
                while True:
                    containers = cli('container', 'list', '--app-id', app_id, '--json')
                    if containers.returncode:
                        raise RuntimeError('Cannot verify container retirement')
                    if not json.loads(containers.stdout):
                        break
                    if time.monotonic() > deadline:
                        raise TimeoutError('Container did not retire')
                    time.sleep(5)
            row = {'cycle': index, 'prior_container_retired': index > 0,
                   'requested_at': datetime.now(timezone.utc).isoformat()}
            report['cycles'].append(row)
            save()
            started = time.perf_counter()
            call = worker.measure.spawn(audio)
            try:
                result = call.get(timeout=300)
            except BaseException:
                call.cancel(terminate_containers=True)
                raise
            row.update(result, rpc_seconds=time.perf_counter()-started)
            save()
            print(json.dumps(row), flush=True)
            assert row['valid_times'] and row['call'] == 1
            assert index == 0 or row['boot_id'] != report['cycles'][index-1]['boot_id']
            assert row['output_sha256'] == report['cycles'][0]['output_sha256']
        report['inference_passed'] = True
    except Exception as error:
        report.update(inference_passed=False, error_type=type(error).__name__)
        print(json.dumps({'error':type(error).__name__}), flush=True)
    finally:
        if app_id is None:
            # Deployment can succeed remotely even if the CLI response times out.
            try:
                apps = json.loads(cli('app', 'list', '--json').stdout)
                app_id = next((a['app_id'] for a in apps
                               if a['description'] == name and a['state'] == 'deployed'), None)
                if app_id:
                    report['app_id'] = app_id
            except Exception as error:
                report['cleanup_lookup_error_type'] = type(error).__name__
        if app_id:
            # Log retrieval must never prevent retiring the paid experiment.
            try:
                logs = cli('app', 'logs', app_id, '--source', 'system', '--tail', '1000', '--timestamps', '--show-container-id')
                (folder/(name+'-system.log')).write_text(logs.stdout+logs.stderr, encoding='utf-8')
                current_lines = []
                for line in logs.stdout.splitlines():
                    try:
                        logged_at = datetime.fromisoformat(line[:25])
                    except ValueError:
                        continue
                    if logged_at >= datetime.fromisoformat(report['at']):
                        current_lines.append(line)
                report['snapshot_log_lines'] = [line for line in current_lines if 'snapshot' in line.lower()]
                retired_requests = [datetime.fromisoformat(row['requested_at']) for row in report['cycles']
                                    if row['prior_container_retired'] and row.get('valid_times')]
                report['restore_log_confirmed'] = logs.returncode == 0 and any(
                    'Restoring Function from memory snapshot' in line
                    and any(datetime.fromisoformat(line[:25]) >= requested for requested in retired_requests)
                    for line in current_lines)
            except Exception as error:
                report['log_error_type'] = type(error).__name__
            finally:
                try:
                    stopped = cli('app', 'stop', app_id, '--yes')
                    report['stop_requested'] = stopped.returncode == 0
                    deadline = time.monotonic()+60
                    while True:
                        apps = json.loads(cli('app', 'list', '--json').stdout)
                        status = next((a for a in apps if a['app_id'] == app_id), {})
                        containers = cli('container', 'list', '--app-id', app_id, '--json')
                        report['stopped'] = (status.get('state') == 'stopped'
                                             and str(status.get('tasks')) == '0'
                                             and containers.returncode == 0
                                             and not json.loads(containers.stdout))
                        if report['stopped'] or time.monotonic() > deadline:
                            break
                        time.sleep(5)
                except Exception as error:
                    report.update(stopped=False, stop_error_type=type(error).__name__)
        save()
    verified = (report.get('inference_passed') and report.get('stopped')
                and (args.control or report.get('restore_log_confirmed')))
    return 0 if verified else 1


if __name__ == '__main__':
    raise SystemExit(main())
