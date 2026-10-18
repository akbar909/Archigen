import os
import sys
import unittest
from unittest.mock import patch


BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from utils import s3_storage


class CloudFrontUrlResolutionTests(unittest.TestCase):
    def test_cloudfront_glb_url_is_preserved(self):
        url = "https://d111111abcdef8.cloudfront.net/outputs/houses/example.glb"
        self.assertEqual(url, s3_storage.resolve_s3_url_to_presigned(url))

    def test_existing_s3_url_uses_configured_cloudfront_domain(self):
        with patch.object(
            s3_storage,
            "AWS_S3_PUBLIC_BASE_URL",
            "https://d111111abcdef8.cloudfront.net",
        ):
            result = s3_storage.resolve_s3_url_to_presigned(
                "https://archigen-storage.s3.us-east-1.amazonaws.com/outputs/houses/example.glb"
            )
        self.assertEqual(
            "https://d111111abcdef8.cloudfront.net/outputs/houses/example.glb",
            result,
        )

    def test_plain_s3_key_uses_configured_cloudfront_domain(self):
        with patch.object(
            s3_storage,
            "AWS_S3_PUBLIC_BASE_URL",
            "https://d111111abcdef8.cloudfront.net/",
        ):
            result = s3_storage.resolve_s3_url_to_presigned(
                "outputs/houses/example.glb"
            )
        self.assertEqual(
            "https://d111111abcdef8.cloudfront.net/outputs/houses/example.glb",
            result,
        )


if __name__ == "__main__":
    unittest.main()
