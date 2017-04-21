import datetime
import os
import shutil
from io import BytesIO
from unittest.mock import patch

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.test import TestCase, override_settings
from django.utils import timezone

from maker.models import Apk, ApkPointer, RemoteApkPointer, App, RemoteApp, RemoteRepository, \
    Repository
from maker.storage import get_apk_file_path
from . import TEST_DIR, TEST_FILES_DIR, datetime_is_recent


@override_settings(MEDIA_ROOT=TEST_DIR)
class ApkTestCase(TestCase):

    def setUp(self):
        # Create APK
        self.apk = Apk.objects.create(package_id="org.example")
        self.apk.file.save('test.apk', BytesIO(b'content'), save=True)

        # Create Repository
        repository = Repository(name="Test", description="Test", url="https://f-droid.org",
                                user_id=1)
        repository.save()

        # Create RemoteRepository
        remote_repository = RemoteRepository.objects.create(
            name='Test',
            description='Test',
            url='https://f-droid.org',
            last_change_date=datetime.datetime.fromtimestamp(0, timezone.utc)
        )

        # Create RemoteApp
        RemoteApp.objects.create(
            repo=remote_repository,
            last_updated_date=datetime.datetime.fromtimestamp(0, timezone.utc)
        )

    def tearDown(self):
        shutil.rmtree(TEST_DIR)

    @patch('maker.tasks.download_apk')
    def test_download_async(self, download_apk):
        """
        Makes sure that the asynchronous download starts a background task.
        """
        # remove file and assert that it is gone
        self.apk.file.delete()
        self.assertFalse(self.apk.file)

        # download apk and assert that the async task has been scheduled
        self.apk.download_async('url')
        download_apk.assert_called_once_with(self.apk.id, 'url')

    @patch('maker.tasks.download_apk')
    def test_download_async_only_when_file_missing(self, download_apk):
        """
        Makes sure that the asynchronous download is not called when apk has a file.
        """
        self.assertTrue(self.apk.file)
        self.apk.download_async('url')
        self.assertFalse(download_apk.called)

    @patch('requests.get')
    def test_download(self, get):
        # remove file and assert that it is gone
        self.apk.file.delete()
        self.assertFalse(self.apk.file)

        # create ApkPointer and assert it doesn't have a file
        apk_pointer = ApkPointer.objects.create(apk=self.apk, repo=Repository.objects.get(id=1))
        self.assertFalse(apk_pointer.file)

        # fake return value of GET request for repository icon
        get.return_value.status_code = requests.codes.ok
        get.return_value.content = b'foo'

        # download file and assert there was a GET request for the URL
        self.apk.download('url/download.apk')
        get.assert_called_once_with('url/download.apk')

        # assert that downloaded file has been saved
        self.assertEqual(get_apk_file_path(self.apk, 'download.apk'), self.apk.file.name)
        path = os.path.join(settings.MEDIA_ROOT, get_apk_file_path(self.apk, 'download.apk'))
        self.assertTrue(os.path.isfile(path))

        # assert that ApkPointer was updated with a new copy/link of the downloaded file
        apk_pointer = ApkPointer.objects.get(pk=apk_pointer.pk)
        self.assertTrue(apk_pointer.file)
        self.assertEqual(get_apk_file_path(apk_pointer, 'download.apk'), apk_pointer.file.name)
        path = os.path.join(settings.MEDIA_ROOT, apk_pointer.file.name)
        self.assertTrue(os.path.isfile(path))

    def test_from_json(self):
        package_info = {
            'packageName': 'org.example',
            'versionName': 'v23',
            'versionCode': '23',
            'size': '42',
            'hash': '0123456789',
            'hashType': 'sha4048',
            'sig': '9876543210',
            'added': 1337,
        }
        apk = Apk.from_json(package_info)
        self.assertEqual(package_info['packageName'], apk.package_id)
        self.assertEqual(package_info['versionName'], apk.version_name)
        self.assertEqual(package_info['versionCode'], apk.version_code)
        self.assertEqual(package_info['size'], apk.size)
        self.assertEqual(package_info['hash'], apk.hash)
        self.assertEqual(package_info['hashType'], apk.hash_type)
        self.assertEqual(package_info['sig'], apk.signature)
        added = datetime.datetime.fromtimestamp(package_info['added'] / 1000, timezone.utc)
        self.assertEqual(added, apk.added_date)
        self.assertFalse(apk.file)
        self.assertFalse(apk.is_downloading)
        self.assertFalse(apk.pk)

    def test_apk_file_gets_deleted(self):
        # get APK and assert that file exists
        apk = self.apk
        file_path = os.path.join(TEST_DIR, apk.file.name)
        self.assertTrue(os.path.isfile(file_path))
        self.assertEqual(apk.file.name, 'test.apk')

        # delete APK and assert that file got deleted as well
        apk.delete()
        self.assertFalse(os.path.isfile(file_path))

    def test_apk_gets_deleted_without_pointers(self):
        # Delete APK and assert that it got deleted
        self.apk.delete_if_no_pointers()
        self.assertFalse(Apk.objects.filter(package_id="org.example").exists())

    def test_apk_does_not_get_deleted_with_pointer(self):
        # Create local pointer
        apk_pointer = ApkPointer(apk=self.apk, repo=Repository.objects.get(id=1))
        apk_pointer.save()

        # Delete APK and assert that it did not get deleted
        self.apk.delete_if_no_pointers()
        self.assertTrue(Apk.objects.filter(package_id="org.example").exists())

    def test_apk_does_not_get_deleted_with_remote_pointer(self):
        # Create remote pointer
        remote_apk_pointer = RemoteApkPointer(apk=self.apk, app=RemoteApp.objects.get(id=1))
        remote_apk_pointer.save()

        # Delete APK and assert that it did not get deleted
        self.apk.delete_if_no_pointers()
        self.assertTrue(Apk.objects.filter(package_id="org.example").exists())


@override_settings(MEDIA_ROOT=TEST_DIR)
class ApkPointerTestCase(TestCase):
    apk_file_name = 'test_1.apk'

    def setUp(self):
        # Create Repository
        repo = Repository.objects.create(user_id=1)

        # Create ApkPointer
        self.apk_pointer = ApkPointer(repo=repo)

        # Attach a real APK file to the pointer
        file_path = os.path.join(TEST_FILES_DIR, self.apk_file_name)
        with open(file_path, 'rb') as f:
            self.apk_pointer.file.save(self.apk_file_name, File(f), save=True)

    @patch('fdroidserver.common.genkeystore')
    def _create_repo(self, genkeystore=None):
        """
        Create the actual repository, so we have the required proper environment.
        It does not create a signing key to save time.
        """
        genkeystore.return_value = ('pubkey', 'fingerprint')
        self.apk_pointer.repo.create()
        self.assertTrue(genkeystore.called)

    def tearDown(self):
        shutil.rmtree(TEST_DIR)

    def test_initialize_rejects_invalid_apk(self):
        # overwrite APK file with rubbish
        self.apk_pointer.file.delete()
        self.apk_pointer.file.save(self.apk_file_name, BytesIO(b'foo'), save=True)

        # initialize the pointer and expect a ValidationError
        with self.assertRaises(ValidationError):
            self.apk_pointer.initialize()

    def test_initialize(self):
        # create the repository environment
        self._create_repo()

        # initialize the ApkPointer with its stored APK file
        self.apk_pointer.initialize()

        # get the created Apk object and assert that it has been created properly
        apk = Apk.objects.get(id=1)
        self.assertEqual('org.bitbucket.tickytacky.mirrormirror', apk.package_id)
        self.assertEqual(2, apk.version_code)
        self.assertEqual('1.0.1', apk.version_name)
        self.assertEqual(7084, apk.size)
        self.assertEqual('91ea97410acda0a4ff86b7504c3a58eb', apk.signature)
        self.assertEqual('64021f6d632eb5ba55bdeb5c4a78ed612bd3facc25d9a8a5d1c9d5d7a6bcc047',
                         apk.hash)
        self.assertEqual('sha256', apk.hash_type)
        self.assertTrue(datetime_is_recent(apk.added_date))
        self.assertFalse(apk.is_downloading)

        # assert that global APK file has been linked/copied properly
        self.assertEqual(get_apk_file_path(apk, self.apk_file_name), apk.file.name)
        self.assertTrue(os.path.isfile(os.path.join(settings.MEDIA_ROOT, apk.file.name)))

        # get the created Apk object and assert that it has been created properly
        app = App.objects.get(pk=1)
        self.assertEqual(self.apk_pointer.repo, app.repo)
        self.assertEqual(apk.package_id, app.package_id)
        self.assertEqual(app.package_id, app.name)  # this apk has no name, so use fallback

        # assert that the app icon has been created properly
        icon_name = app.package_id + '.' + str(apk.version_code) + '.png'
        self.assertTrue(app.icon.name.endswith(icon_name))
        icon_path = os.path.join(settings.MEDIA_ROOT, app.icon.name)
        self.assertTrue(os.path.isfile(icon_path))

    def test_initialize_reuses_existing_apk(self):
        # create the repository environment
        self._create_repo()

        # create existing Apk object with same package_id and hash
        apk = Apk(package_id='org.bitbucket.tickytacky.mirrormirror',
                  hash='64021f6d632eb5ba55bdeb5c4a78ed612bd3facc25d9a8a5d1c9d5d7a6bcc047')
        apk.save()

        # initialize the ApkPointer with its stored APK file
        self.apk_pointer.initialize()

        # assert that the Apk object was re-used
        self.assertTrue(len(Apk.objects.all()) == 1)
        self.assertEqual(apk, self.apk_pointer.apk)

    def test_initialize_reuses_existing_app(self):
        # create the repository environment
        self._create_repo()

        # create existing App object with same repo and package_id
        app = App.objects.create(repo=self.apk_pointer.repo,
                                 package_id='org.bitbucket.tickytacky.mirrormirror')

        # initialize the ApkPointer with its stored APK file
        self.apk_pointer.initialize()

        # assert that the App object was re-used
        self.assertTrue(len(App.objects.all()) == 1)
        self.assertEqual(app, self.apk_pointer.app)

        # assert that existing App object was updated
        app = App.objects.get(pk=app.pk)
        self.assertEqual('org.bitbucket.tickytacky.mirrormirror', app.name)
        self.assertTrue(app.icon)
