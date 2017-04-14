import os
import shutil
from io import BytesIO

from django.test import TestCase, override_settings

from maker.models import Apk
from . import TEST_DIR


@override_settings(MEDIA_ROOT=TEST_DIR)
class ApkTestCase(TestCase):

    def setUp(self):
        apk = Apk.objects.create(package_id="org.example")
        apk.file.save('test.apk', BytesIO(b'content'), save=True)

    def tearDown(self):
        shutil.rmtree(TEST_DIR)

    def test_apk_file_gets_deleted(self):
        # get APK and assert that file exists
        apk = Apk.objects.get(package_id="org.example")
        file_path = os.path.join(TEST_DIR, apk.file.name)
        self.assertTrue(os.path.isfile(file_path))
        self.assertEqual(apk.file.name, 'test.apk')

        # delete APK and assert that file got deleted as well
        apk.delete()
        self.assertFalse(os.path.isfile(file_path))
