import os
import shutil
from io import BytesIO

import datetime

from django.test import TestCase, override_settings
from django.utils import timezone

from maker.models import Apk, ApkPointer, RemoteApkPointer, RemoteApp, RemoteRepository, Repository
from . import TEST_DIR


@override_settings(MEDIA_ROOT=TEST_DIR)
class ApkTestCase(TestCase):

    def setUp(self):
        # Create APK
        apk = Apk.objects.create(package_id="org.example")
        apk.file.save('test.apk', BytesIO(b'content'), save=True)

        # Create Repository
        repository = Repository(name="Test", description="Test", url="https://f-droid.org", user_id=1)
        repository.save()

        # Create RemoteRepository
        remote_repository = RemoteRepository.objects.create(
            name='Test',
            description='Test',
            url='https://f-droid.org',
            last_change_date=datetime.datetime.fromtimestamp(0, timezone.utc)
        )

        # Create RemoteApp
        remote_app = RemoteApp.objects.create(
            repo=remote_repository,
            last_updated_date=datetime.datetime.fromtimestamp(0, timezone.utc)
        )

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

    def test_apk_gets_deleted_without_pointers(self):
        # Get APK
        apk = Apk.objects.get(package_id="org.example")

        # Delete APK and assert that it got deleted
        apk.delete_if_no_pointers()
        self.assertFalse(Apk.objects.filter(package_id="org.example").exists())

    def test_apk_does_not_get_deleted_with_pointer(self):
        # Get APK and Repository
        apk = Apk.objects.get(package_id="org.example")
        repository = Repository.objects.get(id=1)

        # Create remote pointer
        apk_pointer = ApkPointer(apk=apk, repo=repository)
        apk_pointer.save()

        # Delete APK and assert that it did not get deleted
        apk.delete_if_no_pointers()
        self.assertTrue(Apk.objects.filter(package_id="org.example").exists())

    def test_apk_does_not_get_deleted_with_remote_pointer(self):
        # Get APK and RemoteApp
        apk = Apk.objects.get(package_id="org.example")
        remote_app = RemoteApp.objects.get(id=1)

        # Create remote pointer
        remote_apk_pointer = RemoteApkPointer(apk=apk, app=remote_app)
        remote_apk_pointer.save()

        # Delete APK and assert that it did not get deleted
        apk.delete_if_no_pointers()
        self.assertTrue(Apk.objects.filter(package_id="org.example").exists())
