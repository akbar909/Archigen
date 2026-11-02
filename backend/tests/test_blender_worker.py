"""Worker failures retain the Blender error across stdout/stderr and restarts."""
import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


WORKER_FILE = Path(__file__).resolve().parents[2] / 'blender' / 'worker_server.py'
SPEC = importlib.util.spec_from_file_location('worker_diagnostics_test_module', WORKER_FILE)
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


class BlenderWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='archigen-worker-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs, self.outputs = self.root / 'input', self.root / 'output'
        self.inputs.mkdir()
        self.outputs.mkdir()
        for name, value in [('INPUT_DIR',str(self.inputs)),('OUTPUT_DIR',str(self.outputs)),('AWS_S3_BUCKET','')]:
            context = patch.object(worker,name,value)
            context.start()
            self.addCleanup(context.stop)
        self.client = worker.app.test_client()

    def generate(self, payload=None):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            response = self.client.post('/generate',json=payload or {'layout':{'house_id':'test_house'}})
        return response, output.getvalue()

    def test_python_error_on_stdout_is_returned_and_both_streams_are_persisted(self):
        stdout = '[ARCHGEN] Building walls\nTraceback (most recent call last):\n  File "script.py", line 12\nKeyError: \'Roughness\'\n'
        stderr = 'Blender startup diagnostics\n'
        with patch.object(worker.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout=stdout,stderr=stderr)):
            response, console = self.generate()
        data = response.get_json()
        self.assertEqual(500,response.status_code)
        self.assertEqual("KeyError: 'Roughness'",data['reason'])
        self.assertEqual(1,data['returncode'])
        self.assertIn(stdout,console)
        self.assertIn(stderr,console)
        log = (self.outputs / data['log_file']).read_text(encoding='utf-8')
        self.assertIn(stdout,log)
        self.assertIn(stderr,log)
        metadata = json.loads(log.splitlines()[0])
        self.assertEqual('failed',metadata['status'])
        self.assertEqual(data['reason'],metadata['reason'])
        self.assertEqual(worker.BLENDER_GENERATION_TIMEOUT_SECONDS,metadata['generation_timeout_seconds'])

    def test_exception_on_stderr_is_not_lost_when_stdout_contains_normal_progress(self):
        reason = worker.blender_failure_reason(1,'Blender quit\n','Traceback:\nRuntimeError: Furniture inventory mismatch\n')
        self.assertEqual('RuntimeError: Furniture inventory mismatch',reason)

    def test_signal_kill_is_a_memory_hint_instead_of_a_definite_oom_claim(self):
        for code in (-9,137):
            with self.subTest(code=code):
                reason = worker.blender_failure_reason(code)
                self.assertIn('Possible memory exhaustion',reason)
        self.assertIn('segmentation fault',worker.blender_failure_reason(-11))
        self.assertIn('code 2',worker.blender_failure_reason(2))

    def test_timeout_retains_partial_output_and_remains_http_504(self):
        error = subprocess.TimeoutExpired(['blender'],600,output=b'partial Blender progress\xff',stderr=b'partial stderr')
        with patch.object(worker.subprocess,'run',side_effect=error):
            response, console = self.generate()
        data = response.get_json()
        self.assertEqual(504,response.status_code)
        self.assertIn('timed out',data['reason'])
        self.assertIn('partial Blender progress',data['stdout'])
        self.assertIn('partial stderr',data['details'])
        self.assertIn('partial Blender progress',console)
        metadata = json.loads((self.outputs / data['log_file']).read_text(encoding='utf-8').splitlines()[0])
        self.assertEqual('timed_out',metadata['status'])

    def test_missing_binary_retains_launch_reason_in_a_diagnostic_log(self):
        with patch.object(worker.subprocess,'run',side_effect=FileNotFoundError('blender executable not found')):
            response, _ = self.generate()
        data = response.get_json()
        self.assertEqual(500,response.status_code)
        self.assertIn('FileNotFoundError',data['reason'])
        self.assertTrue((self.outputs / data['log_file']).exists())

    def test_successful_exit_without_glb_is_not_reported_as_a_successful_build(self):
        with patch.object(worker.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='Blender quit',stderr='')):
            response, _ = self.generate()
        data = response.get_json()
        self.assertEqual(500,response.status_code)
        self.assertIn('without creating',data['reason'])
        metadata = json.loads((self.outputs / data['log_file']).read_text(encoding='utf-8').splitlines()[0])
        self.assertEqual('failed',metadata['status'])

    def test_successful_generation_keeps_model_response_and_writes_log(self):
        def complete(*args,**kwargs):
            (self.outputs / 'test_house.glb').write_bytes(b'glTFtest')
            return SimpleNamespace(returncode=0,stdout='Export complete\n',stderr='')
        with patch.object(worker.subprocess,'run',side_effect=complete):
            response, _ = self.generate()
        data = response.get_json()
        self.assertEqual(200,response.status_code)
        self.assertTrue(data['success'])
        self.assertEqual(8,data['file_size_bytes'])
        self.assertTrue(data['glb_url'].endswith('/models/test_house.glb'))
        metadata = json.loads((self.outputs / data['log_file']).read_text(encoding='utf-8').splitlines()[0])
        self.assertEqual('completed',metadata['status'])

    def test_safe_input_ids_and_layout_types_are_checked_before_running_blender(self):
        with patch.object(worker.subprocess,'run') as run:
            for payload in [{'layout':[]},{'layout':{'house_id':'../../escape'}},{'layout':{'house_id':'..\\escape'}}]:
                response, _ = self.generate(payload)
                self.assertEqual(400,response.status_code)
            run.assert_not_called()
        self.assertEqual([],list(self.inputs.iterdir()))

    def test_diagnostic_logs_are_not_exposed_by_the_public_model_route(self):
        (self.outputs / 'private.log').write_text('Blender diagnostic output',encoding='utf-8')
        self.assertEqual(404,self.client.get('/models/private.log').status_code)

    def test_health_reports_timeout_and_running_code_separately_from_downloaded_file(self):
        completed = SimpleNamespace(returncode=0,stdout='Blender 3.6.14\n')
        with patch.object(worker.subprocess,'run',return_value=completed), patch.object(worker,'file_sha256',return_value='new-disk-hash'):
            response = self.client.get('/health')
        data = response.get_json()
        self.assertEqual(200,response.status_code)
        self.assertEqual('healthy',data['status'])
        self.assertEqual(worker.BLENDER_GENERATION_TIMEOUT_SECONDS,data['generation_timeout_seconds'])
        self.assertEqual(worker.WORKER_SHA256,data['worker_sha256'])
        self.assertTrue(data['restart_required'])

    def test_failed_blender_version_check_is_not_healthy(self):
        with patch.object(worker.subprocess,'run',side_effect=FileNotFoundError('missing blender')):
            response = self.client.get('/health')
        self.assertEqual(503,response.status_code)
        self.assertEqual('unhealthy',response.get_json()['status'])


if __name__ == '__main__':
    unittest.main()
