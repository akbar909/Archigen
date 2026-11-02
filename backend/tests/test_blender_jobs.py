"""Background builds expose real failures and do not start duplicate workers."""
import copy
import datetime as dt
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bson import ObjectId
from flask import Flask, request
import requests
from routes.chat import approve_layout_for_version, generate_3d_for_version, _generation_status, _start_3d_generation, _serialize_version
from utils.blender_service import BlenderGenerationError, generate_3d_house_model
from utils.blender_failures import worker_failure_reason


class VersionCollection:
    def __init__(self, version):
        self.version = copy.deepcopy(version)

    def find_one(self, query):
        return copy.deepcopy(self.version)

    def update_one(self, query, update):
        job = self.version.get('generation_3d', {})
        if 'generation_3d.job_id' in query and query['generation_3d.job_id'] != job.get('job_id'):
            return SimpleNamespace(matched_count=0)
        for path, value in update.get('$set', {}).items():
            target = self.version
            keys = path.split('.')
            for key in keys[:-1]:
                target = target.setdefault(key, {})
            target[keys[-1]] = copy.deepcopy(value)
        return SimpleNamespace(matched_count=1)


class BlenderJobTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.version = {'_id':ObjectId(), 'project_id':ObjectId(), 'user_id':ObjectId(),
                        'version_num':1, 'design':{'layout_approved':True}, 'glb_url':'old.glb'}
        self.collection = VersionCollection(self.version)
        self.tasks = []
        def thread(target, **kwargs):
            return Mock(start=lambda: self.tasks.append(target))
        self.stack = [patch('routes.chat.versions_collection',return_value=self.collection),
                      patch('routes.chat.threading.Thread',side_effect=thread),
                      patch('routes.chat.resolve_s3_url_to_presigned',side_effect=lambda value:value),
                      patch('routes.chat.validate_and_repair_design',side_effect=lambda design,**kwargs:(copy.deepcopy(design),{'critical_errors':[]}))]
        for item in self.stack:
            item.start()
            self.addCleanup(item.stop)

    def call(self, view, body=None):
        with self.app.test_request_context(method='POST',json=body or {}):
            request.user = {'_id':self.version['user_id']}
            return view.__wrapped__(str(self.version['project_id']),str(self.version['_id']))

    def test_approval_and_retry_return_immediately_and_running_build_is_reused(self):
        with patch('routes.chat.generate_3d_house_model',return_value='new.glb') as generate:
            response, status = self.call(approve_layout_for_version)
            self.assertEqual(202,status)
            self.assertTrue(response.get_json()['pending'])
            self.assertEqual(1,len(self.tasks))
            generate.assert_not_called()
            response, status = self.call(generate_3d_for_version,{'force':True})
            self.assertTrue(response.get_json()['already_running'])
            self.assertEqual(1,len(self.tasks))
            self.tasks[0]()
            self.assertEqual('completed',self.collection.version['generation_3d']['status'])
            self.assertEqual('new.glb',self.collection.version['design']['glb_url'])

    def test_real_worker_failure_is_saved_and_returned_in_version_status(self):
        with patch('routes.chat.generate_3d_house_model',side_effect=BlenderGenerationError('Cannot reach the Blender worker.')):
            self.call(approve_layout_for_version)
            with self.assertLogs(level='ERROR'):
                self.tasks[0]()
        serialized = _serialize_version(self.collection.version)
        self.assertEqual('failed',serialized['generation_3d']['status'])
        self.assertEqual('Cannot reach the Blender worker.',serialized['generation_3d']['error'])
        self.assertEqual('old.glb',serialized['glb_url'])

    def test_failed_build_can_retry_without_accepting_a_stale_completion(self):
        self.call(approve_layout_for_version)
        old_job = self.collection.version['generation_3d']['job_id']
        self.collection.version['generation_3d']['status'] = 'failed'
        self.call(generate_3d_for_version,{'force':True})
        self.assertNotEqual(old_job,self.collection.version['generation_3d']['job_id'])
        with patch('routes.chat.generate_3d_house_model',return_value='stale.glb'):
            self.tasks[0]()
        self.assertEqual('running',self.collection.version['generation_3d']['status'])
        self.assertEqual('old.glb',self.collection.version['glb_url'])
        with patch('routes.chat.generate_3d_house_model',return_value='new.glb'):
            self.tasks[1]()
        self.assertEqual('new.glb',self.collection.version['glb_url'])

    def test_atomic_claim_rejects_two_starts_using_the_same_version_snapshot(self):
        self.assertTrue(_start_3d_generation(copy.deepcopy(self.version),self.version['design'],'project'))
        self.assertFalse(_start_3d_generation(copy.deepcopy(self.version),self.version['design'],'project'))
        self.assertEqual(1,len(self.tasks))

    def test_abandoned_build_becomes_timed_out_and_can_be_retried(self):
        self.version['generation_3d'] = {'job_id':'abandoned', 'status':'running', 'timeout_seconds':690,
                                        'started_at':(dt.datetime.utcnow()-dt.timedelta(minutes=20)).isoformat()}
        self.collection.version = copy.deepcopy(self.version)
        self.assertEqual('timed_out',_generation_status(self.version)['status'])
        response, status = self.call(generate_3d_for_version,{'force':True})
        self.assertEqual(202,status)
        self.assertEqual('running',response.get_json()['version']['generation_3d']['status'])


class BlenderServiceFailures(unittest.TestCase):
    def call(self):
        return generate_3d_house_model({},raise_on_error=True)

    def test_disabled_generation_is_an_explicit_failure(self):
        with patch('utils.blender_service.BLENDER_ENABLED',False):
            with self.assertRaisesRegex(BlenderGenerationError,'disabled'):
                self.call()

    def test_legacy_worker_stdout_exposes_the_actual_python_exception(self):
        payload = {'error':'Blender generation process failed', 'details':'',
                   'stdout':'Blender 3.6.14\nError: Python: Traceback (most recent call last):\n  File "generate_house.py", line 10\nModuleNotFoundError: No module named s3_asset_resolver\n\nBlender quit'}
        self.assertEqual('ModuleNotFoundError: No module named s3_asset_resolver', worker_failure_reason(payload))

    def test_new_worker_reason_and_process_signals_are_preserved(self):
        self.assertEqual('A required asset is missing.', worker_failure_reason({'reason':'A required asset is missing.'}))
        self.assertIn('SIGKILL', worker_failure_reason({'returncode':-9}))
        self.assertIn('segmentation fault', worker_failure_reason({'returncode':-11}))

    @patch('utils.blender_service.BLENDER_ENABLED',True)
    @patch('utils.blender_service.adapt_gemini_to_blender_layout',return_value={'house_id':'test'})
    def test_process_failure_reason_reaches_the_job_error_instead_of_generic_text(self, _adapt):
        response = Mock(status_code=500, text='worker failed')
        response.json.return_value = {'error':'Blender generation process failed',
                                      'stdout':'Traceback (most recent call last):\nRuntimeError: Scene validation failed: missing furniture asset'}
        with patch('utils.blender_service.requests.post',return_value=response):
            with self.assertRaisesRegex(BlenderGenerationError,'missing furniture asset'):
                self.call()

    @patch('utils.blender_service.BLENDER_ENABLED',True)
    @patch('utils.blender_service.adapt_gemini_to_blender_layout',return_value={'house_id':'test'})
    def test_connection_timeout_and_process_errors_are_distinct(self, _adapt):
        for exception, message in [(requests.ConnectionError(),'Cannot reach'),(requests.Timeout(),'did not finish')]:
            with self.subTest(message=message), patch('utils.blender_service.requests.post',side_effect=exception):
                with self.assertRaisesRegex(BlenderGenerationError,message):
                    self.call()
        response = Mock(status_code=500,text='worker failed')
        response.json.return_value = {'error':'Blender generation process failed'}
        with patch('utils.blender_service.requests.post',return_value=response):
            with self.assertRaisesRegex(BlenderGenerationError,r'500.*process failed'):
                self.call()


if __name__ == '__main__':
    unittest.main()
