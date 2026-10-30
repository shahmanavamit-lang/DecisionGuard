"""Trusted fixed worker executable. No plugins, arbitrary Python or model service.

Run by the broker using isolated Python. The process sees plans and approved tool
results only, never credentials or a database path. Audit restrictions are defense
in depth, not a security claim about arbitrary code with the same OS identity.
"""
import hashlib
import json
import math
import os
import resource
import socket
import sys

MAX_FRAME = 8 * 1024 * 1024


def restrict(seconds):
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    cpu = max(1, math.ceil(seconds))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    if sys.platform.startswith('linux'):
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))

    def deny(event, args):
        if event in {'open', 'os.system', 'os.listdir', 'os.scandir', 'os.chdir',
                     'os.remove', 'os.rename', 'os.mkdir', 'os.rmdir', 'subprocess.Popen',
                     'ctypes.dlopen'} or event.startswith(('socket.', 'os.exec', 'os.spawn')):
            raise PermissionError('Worker capability unavailable: ' + event)
    sys.addaudithook(deny)


def receive():
    line = sys.stdin.buffer.readline(MAX_FRAME + 1)
    if not line or len(line) > MAX_FRAME or not line.endswith(b'\n'):
        raise ValueError('Missing or oversized broker frame')
    return json.loads(line)


def send(data):
    raw = json.dumps(data, ensure_ascii=True).encode() + b'\n'
    if len(raw) > MAX_FRAME:
        raise ValueError('Worker frame exceeds limit')
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


def main():
    seconds = float(sys.argv[1])
    probe = sys.argv[2] if len(sys.argv) > 2 else None
    restrict(seconds)
    if probe is not None:
        blocked = {}
        for name, fn in [('file', lambda: open(probe, 'rb')), ('network', lambda: socket.socket()),
                         ('shell', lambda: os.system('true'))]:
            try:
                fn()
                blocked[name] = False
            except PermissionError:
                blocked[name] = True
        send({'blocked': blocked, 'environment_keys': sorted(os.environ)})
        return
    plan = receive()
    observations = {}
    for index, step in enumerate(plan['steps']):
        kind = step['kind']
        if kind == 'receive':
            proposal = {'kind': 'receive', 'index': index, 'output_id': step['output_id']}
        else:
            content = ''
            if kind == 'summarize':
                text = observations[step['source']]['content']
                content = json.dumps({'algorithm': 'text-statistics-v1', 'characters': len(text),
                                      'words': len(text.split()), 'lines': len(text.splitlines()),
                                      'utf8_bytes': len(text.encode('utf-8')),
                                      'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()}, sort_keys=True)
            proposal = {'kind': 'action', 'index': index,
                        'operation': 'read_file' if kind == 'read' else 'write_note',
                        'resource_id': step['resource_id'], 'resource_version': step['resource_version'],
                        'content': content}
        send(proposal)
        response = receive()
        if response.get('status') != 'completed':
            return
        observations[index] = response['output']
    send({'kind': 'done', 'steps': len(plan['steps'])})


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Do not echo documents or exception payloads into process diagnostics.
        sys.exit(2)
