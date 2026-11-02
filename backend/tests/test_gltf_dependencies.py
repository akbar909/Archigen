"""A cached glTF is importable only when its buffers and textures are present."""
import contextlib
import importlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[2] / 'blender' / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0,str(SCRIPTS))
resolver = importlib.import_module('s3_asset_resolver')
importer = importlib.import_module('import_asset')
sync = importlib.import_module('sync_s3_assets')


class FakeS3:
    def __init__(self, objects):
        self.objects, self.downloads = objects, []

    def download_file(self, bucket, key, destination):
        self.downloads.append(key)
        if key not in self.objects:
            raise FileNotFoundError(key)
        Path(destination).write_bytes(self.objects[key])


class GltfDependencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='archigen-gltf-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / 'assets' / 'furniture' / 'sofas'
        self.folder.mkdir(parents=True)
        self.model = self.folder / 'Sofa_01_4k.gltf'
        self.document = {'asset':{'version':'2.0'},'buffers':[{'uri':'Sofa_01.bin','byteLength':8}],
                         'images':[{'uri':'textures/sofa%20fabric.jpg'}]}
        self.model.write_text(json.dumps(self.document),encoding='utf-8')
        self.console = contextlib.redirect_stdout(io.StringIO())
        self.console.__enter__()
        self.addCleanup(self.console.__exit__,None,None,None)

    def test_cached_json_downloads_missing_binary_and_percent_encoded_texture(self):
        client = FakeS3({'assets/furniture/sofas/Sofa_01.bin':b'12345678',
                         'assets/furniture/sofas/textures/sofa fabric.jpg':b'jpeg'})
        with patch.object(resolver,'get_s3_client',return_value=client):
            result = resolver.download_asset_if_missing('assets/furniture/sofas/Sofa_01_4k.gltf',str(self.root),'test')
        self.assertEqual(str(self.model),result)
        self.assertEqual(b'12345678',(self.folder / 'Sofa_01.bin').read_bytes())
        self.assertEqual(b'jpeg',(self.folder / 'textures' / 'sofa fabric.jpg').read_bytes())
        self.assertEqual(2,len(client.downloads))
        self.assertEqual([],list(self.folder.rglob('*.tmp')))

    def test_complete_local_asset_is_a_cache_hit_without_s3_credentials(self):
        (self.folder / 'Sofa_01.bin').write_bytes(b'12345678')
        (self.folder / 'textures').mkdir()
        (self.folder / 'textures' / 'sofa fabric.jpg').write_bytes(b'jpeg')
        with patch.object(resolver,'get_s3_client') as client:
            self.assertEqual(str(self.model),resolver.ensure_model_ready(str(self.model)))
            client.assert_not_called()

    def test_newly_downloaded_gltf_brings_its_dependencies_from_the_same_prefix(self):
        self.model.unlink()
        client = FakeS3({'furniture/sofas/Sofa_01_4k.gltf':json.dumps(self.document).encode(),
                         'furniture/sofas/Sofa_01.bin':b'12345678',
                         'furniture/sofas/textures/sofa fabric.jpg':b'jpeg'})
        with patch.object(resolver,'get_s3_client',return_value=client):
            result = resolver.download_asset_if_missing('assets/furniture/sofas/Sofa_01_4k.gltf',str(self.root),'test')
        self.assertEqual(str(self.model),result)
        self.assertTrue((self.folder / 'Sofa_01.bin').is_file())
        self.assertIn('furniture/sofas/textures/sofa fabric.jpg',client.downloads)

    def test_embedded_buffers_and_buffer_view_images_need_no_download(self):
        self.document.update(buffers=[{'uri':'data:application/octet-stream;base64,AAAA','byteLength':3}],images=[{'bufferView':0}])
        self.model.write_text(json.dumps(self.document),encoding='utf-8')
        with patch.object(resolver,'get_s3_client') as client:
            self.assertEqual(str(self.model),resolver.ensure_model_ready(str(self.model)))
            client.assert_not_called()

    def test_source_glb_fallback_is_same_model_and_resolution_aware(self):
        source = self.folder / 'sofa_01.glb'
        source.write_bytes(b'glTF-source-model')
        (self.folder / 'L_shaped_sofa_02.glb').write_bytes(b'other-sofa')
        with patch.object(resolver,'get_s3_client') as client:
            self.assertEqual(str(source),resolver.ensure_model_ready(str(self.model)))
            client.assert_not_called()
            self.model.unlink()
            self.assertEqual(str(source),resolver.ensure_model_ready(str(self.model)))
            client.assert_not_called()

    def test_missing_dependencies_never_return_a_successful_cache_hit_or_other_sofa(self):
        (self.folder / 'L_shaped_sofa_02.glb').write_bytes(b'other-sofa')
        with patch.object(resolver,'get_s3_client',return_value=None):
            with self.assertRaisesRegex(resolver.AssetDependencyError,r'Sofa_01.bin.*textures/sofa fabric.jpg'):
                resolver.ensure_model_ready(str(self.model))
            self.assertIsNone(resolver.download_asset_if_missing('assets/furniture/sofas/Sofa_01_4k.gltf',str(self.root)))

    def test_truncated_binary_is_repaired_atomically_before_becoming_a_cache_hit(self):
        (self.folder / 'Sofa_01.bin').write_bytes(b'bad')
        client = FakeS3({'assets/furniture/sofas/Sofa_01.bin':b'12345678',
                         'assets/furniture/sofas/textures/sofa fabric.jpg':b'jpeg'})
        with patch.object(resolver,'get_s3_client',return_value=client):
            resolver.ensure_model_ready(str(self.model))
        self.assertEqual(b'12345678',(self.folder / 'Sofa_01.bin').read_bytes())

    def test_relative_shared_textures_are_allowed_within_assets_and_escape_uris_are_rejected(self):
        for uri in ['../../../../escape.bin','%2Fetc/passwd','https://example.com/model.bin','C:/private.bin']:
            with self.subTest(uri=uri), patch.object(resolver,'get_s3_client') as client:
                self.document['buffers'][0]['uri'] = uri
                self.model.write_text(json.dumps(self.document),encoding='utf-8')
                with self.assertRaises(resolver.AssetDependencyError):
                    resolver.ensure_model_ready(str(self.model))
                client.assert_not_called()
        self.document.update(buffers=[{'uri':'../shared.bin','byteLength':8}],images=[])
        self.model.write_text(json.dumps(self.document),encoding='utf-8')
        self.folder.parent.joinpath('shared.bin').write_bytes(b'12345678')
        self.assertEqual(str(self.model),resolver.ensure_model_ready(str(self.model)))

    def test_importer_checks_dependencies_before_invoking_blender(self):
        fake_bpy = Mock()
        fake_bpy.context.scene.objects = []
        with patch.object(importer,'bpy',fake_bpy), patch.object(resolver,'get_s3_client',return_value=None):
            with self.assertRaises(resolver.AssetDependencyError):
                importer.load_model(str(self.model))
            fake_bpy.ops.import_scene.gltf.assert_not_called()

    def test_importer_uses_actual_source_glb_instead_of_the_incomplete_gltf(self):
        source = self.folder / 'sofa_01.glb'
        source.write_bytes(b'glTF-source-model')
        fake_bpy = Mock()
        fake_bpy.context.scene.objects = []
        fake_bpy.ops.import_scene.gltf.side_effect = RuntimeError('import reached')
        with patch.object(importer,'bpy',fake_bpy), patch.object(resolver,'get_s3_client') as client:
            with self.assertRaisesRegex(RuntimeError,'import reached'):
                importer.load_model(str(self.model))
            fake_bpy.ops.import_scene.gltf.assert_called_once_with(filepath=str(source))
            client.assert_not_called()

    def test_full_sync_uploads_bin_and_images_alongside_gltf(self):
        (self.folder / 'Sofa_01.bin').write_bytes(b'12345678')
        (self.folder / 'textures').mkdir()
        (self.folder / 'textures' / 'sofa fabric.jpg').write_bytes(b'jpeg')
        client = Mock()
        client.head_object.return_value = None
        with patch.object(sync,'RUNTIME_BUNDLE',()):
            changed, _, failed = sync.upload_assets(str(self.root),'test',s3_client=client)
        keys = {call.args[2] for call in client.upload_file.call_args_list}
        self.assertEqual(3,changed)
        self.assertEqual(0,failed)
        self.assertIn('assets/furniture/sofas/Sofa_01.bin',keys)
        self.assertIn('assets/furniture/sofas/textures/sofa fabric.jpg',keys)

    def test_resolver_is_part_of_required_runtime_bundle(self):
        self.assertIn(('scripts/s3_asset_resolver.py','scripts/s3_asset_resolver.py'),sync.RUNTIME_BUNDLE)


LOCAL_BLENDER = (os.environ.get('ARCHIGEN_TEST_BLENDER')
                 or ('C:/Program Files/Blender Foundation/Blender 5.1/blender.exe'
                     if Path('C:/Program Files/Blender Foundation/Blender 5.1/blender.exe').is_file()
                     else shutil.which('blender')))


class GltfSourceImportIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(LOCAL_BLENDER and Path(LOCAL_BLENDER).is_file(), 'A local Blender executable is required')
    def test_exact_cloud_failure_assets_import_their_original_source_glbs(self):
        root = Path(__file__).resolve().parents[2]
        targets = [
            (str(root / 'blender/assets/architecture/windows/arched/arched_window_01.gltf'), 'arched_window_01.glb'),
            (str(root / 'blender/assets/furniture/living_room/sofas/Sofa_01_4k.gltf'), 'sofa_01.glb'),
        ]
        source = f"""
import sys
sys.path.insert(0, {str(SCRIPTS)!r})
import bpy
import import_asset
import s3_asset_resolver
s3_asset_resolver.get_s3_client = lambda: None
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for path, expected_source in {targets!r}:
    obj = import_asset.load_model(path, name_prefix='DependencyRegression')
    meshes = [child for child in [obj] + list(obj.children_recursive) if child.type == 'MESH']
    assert meshes, f'No source meshes imported for {{path}}'
    assert sum(len(mesh.data.vertices) for mesh in meshes) > 0, f'Empty imported geometry: {{path}}'
    assert obj.get('archgen_source_file') == expected_source, (path, obj.get('archgen_source_file'))
    print('[ASSET_IMPORT_TEST] ' + expected_source + ': real meshes imported', flush=True)
"""
        with tempfile.TemporaryDirectory(prefix='archigen-gltf-blender-') as folder:
            env = {**os.environ, 'TEMP':folder, 'TMP':folder, 'TMPDIR':folder}
            process = subprocess.run([LOCAL_BLENDER,'--background','--factory-startup','--python-exit-code','1',
                                      '--python-expr',source], capture_output=True, text=True,
                                     encoding='utf-8', errors='replace', timeout=120, env=env)
        output = process.stdout + '\n' + process.stderr
        self.assertEqual(0,process.returncode,output[-14000:])
        for _, expected_source in targets:
            self.assertIn('[ASSET_IMPORT_TEST] ' + expected_source + ': real meshes imported',output)
        for failure in ('Missing resource','FileNotFoundError','could not load buffer','[ERROR]'):
            self.assertNotIn(failure,output)


if __name__ == '__main__':
    unittest.main()
