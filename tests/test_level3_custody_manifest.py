import unittest

from tools.level3_staging.custody_manifest import (
    ManifestDenied,
    make_manifest,
    verify_manifest,
)


class ManifestTests(unittest.TestCase):
    def test_round_trip(self):
        manifest = make_manifest("parent", "file", b"ciphertext")
        self.assertTrue(verify_manifest(manifest, b"ciphertext"))
        self.assertNotIn("ciphertext", str(manifest))

    def test_corrupt_readback(self):
        manifest = make_manifest("parent", "file", b"ciphertext")
        with self.assertRaises(ManifestDenied):
            verify_manifest(manifest, b"ciphertexu")

    def test_invalid_identity(self):
        with self.assertRaises(ManifestDenied):
            make_manifest("", "file", b"x")

    def test_boolean_size_rejected(self):
        manifest = make_manifest("parent", "file", b"x")
        manifest["size"] = True
        with self.assertRaises(ManifestDenied):
            verify_manifest(manifest, b"x")

    def test_extra_fields_rejected(self):
        manifest = make_manifest("parent", "file", b"x")
        manifest["token"] = "secret"
        with self.assertRaises(ManifestDenied):
            verify_manifest(manifest, b"x")
