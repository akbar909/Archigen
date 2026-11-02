"""Recover useful Blender errors from both current and older worker responses."""
import re


def worker_failure_reason(payload):
    if not isinstance(payload, dict):
        return 'The worker returned an invalid response.'
    explicit = payload.get('reason')
    if isinstance(explicit, str) and explicit.strip():
        return ' '.join(explicit.split())[:320]
    streams = '\n'.join(str(payload.get(key) or '') for key in ('details', 'stderr', 'stdout'))
    exceptions = re.findall(r'^\s*((?:[\w.]+Error|[\w.]*Exception|AssertionError|SystemExit):[^\n]+)', streams, re.M)
    if exceptions:
        return ' '.join(exceptions[-1].split())[:320]
    code = payload.get('returncode')
    if code in (-9, 137):
        return 'Blender was killed (SIGKILL). Check the EC2/container memory limit and kernel OOM logs.'
    if code in (-11, 139):
        return 'Blender crashed with a segmentation fault. Check the worker process log.'
    # Older workers can return Blender's explicit failure without a traceback.
    messages = re.findall(r'^\s*(?:\[ERROR\]|Error:)\s*(.+)$', streams, re.M)
    if messages:
        return ' '.join(messages[-1].split())[:320]
    return str(payload.get('error') or 'Generation failed; check the worker process log.')[:320]
