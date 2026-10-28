import os
import sys
import unittest
from unittest.mock import Mock, patch


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import asset_catalog, s3_storage


class CatalogInventoryTests(unittest.TestCase):
    def setUp(self):
        for patcher in (
            patch.object(asset_catalog, '_inventory_keys', []),
            patch.object(asset_catalog, '_inventory_refresh_at', 0.0),
            patch.object(asset_catalog, 'AWS_S3_BUCKET', 'test-bucket'),
            patch.object(asset_catalog, 'monotonic', return_value=1000.0),
            patch.object(asset_catalog, 'get_s3_client'),
        ):
            value = patcher.start()
            self.addCleanup(patcher.stop)
            if patcher.attribute == 'get_s3_client':
                self.client_factory = value
            elif patcher.attribute == 'monotonic':
                self.clock = value
        self.paginator = self.client_factory.return_value.get_paginator.return_value
        self.key = 'assets/furniture/bedroom/beds/bed_03.glb'

    def test_successful_inventory_is_paginated_and_cached(self):
        self.paginator.paginate.return_value = [
            {'Contents': [{'Key': 'assets/'}, {'Key': self.key}]},
            {'Contents': [{'Key': 'assets/textures/walls/brick.jpg'}]},
        ]
        expected = [self.key, 'assets/textures/walls/brick.jpg']
        self.assertEqual(expected, asset_catalog._s3_keys())
        self.assertEqual(expected, asset_catalog._s3_keys())
        self.paginator.paginate.assert_called_once_with(Bucket='test-bucket', Prefix='assets/')
        self.client_factory.assert_called_once_with(catalog=True)

    def test_timeout_uses_local_fallback_and_waits_before_retrying(self):
        self.paginator.paginate.side_effect = TimeoutError('S3 read timed out')
        with patch.object(asset_catalog, '_local_keys', return_value=[self.key]):
            for _ in range(2):
                entries, source = asset_catalog.list_uploaded_assets()
                self.assertEqual('local_sync', source)
                self.assertEqual('bed_03', entries[0]['id'])
        self.paginator.paginate.assert_called_once()
        self.clock.return_value = 1061.0
        self.paginator.paginate.side_effect = None
        self.paginator.paginate.return_value = [{'Contents': [{'Key': self.key}]}]
        self.assertEqual([self.key], asset_catalog._s3_keys())
        self.assertEqual(2, self.paginator.paginate.call_count)

    def test_partial_failure_preserves_previous_s3_inventory(self):
        self.paginator.paginate.return_value = [{'Contents': [{'Key': self.key}]}]
        asset_catalog._s3_keys()
        self.clock.return_value = 1301.0

        def failed_pages():
            yield {'Contents': [{'Key': 'assets/partial.glb'}]}
            raise TimeoutError('second page timed out')

        self.paginator.paginate.return_value = failed_pages()
        entries, source = asset_catalog.list_uploaded_assets()
        self.assertEqual('s3', source)
        self.assertEqual([self.key], [entry['s3_key'] for entry in entries])
        self.assertEqual([self.key], asset_catalog._s3_keys())
        self.assertEqual(2, self.paginator.paginate.call_count)

    def test_successful_empty_refresh_clears_old_inventory(self):
        self.paginator.paginate.return_value = [{'Contents': [{'Key': self.key}]}]
        asset_catalog._s3_keys()
        self.clock.return_value = 1301.0
        self.paginator.paginate.return_value = [{}]
        self.assertEqual([], asset_catalog._s3_keys())


class CatalogClientTests(unittest.TestCase):
    def test_catalog_timeouts_do_not_change_regular_client(self):
        s3_storage.get_s3_client.cache_clear()
        self.addCleanup(s3_storage.get_s3_client.cache_clear)
        with patch.object(s3_storage, 'boto3', Mock()) as sdk, patch.multiple(
            s3_storage, AWS_ACCESS_KEY_ID='test', AWS_SECRET_ACCESS_KEY='test'
        ):
            s3_storage.get_s3_client(catalog=True)
            config = sdk.client.call_args.kwargs['config']
            self.assertEqual(3, config.connect_timeout)
            self.assertEqual(5, config.read_timeout)
            self.assertEqual({'total_max_attempts': 1}, config.retries)
            s3_storage.get_s3_client()
            self.assertNotIn('config', sdk.client.call_args.kwargs)


if __name__ == '__main__':
    unittest.main()
