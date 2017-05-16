import os
import shutil
from datetime import datetime
from io import BytesIO
from unittest.mock import patch

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files import File
from django.test import TestCase, override_settings
from django.utils import timezone
from fdroidserver.update import get_all_icon_dirs

from maker.models import Apk, ApkPointer, RemoteApkPointer, App, RemoteApp, RemoteRepository, \
    Repository
from maker.storage import get_apk_file_path
from .. import TEST_DIR, TEST_FILES_DIR, TEST_PRIVATE_DIR, datetime_is_recent, fake_repo_create


@override_settings(MEDIA_ROOT=TEST_DIR)
class ApkTestCase(TestCase):

    def setUp(self):
        # Create APK
        self.apk = Apk.objects.create(package_id="org.example")
        self.apk.file.save('test.apk', BytesIO(b'content'), save=True)

        # Create Repository
        Repository.objects.create(name="Test", description="Test", url="https://f-droid.org",
                                  user=User.objects.create(username='user2'))

        # Create RemoteRepository
        remote_repository = RemoteRepository.objects.create(
            name='Test',
            description='Test',
            url='https://f-droid.org',
            last_change_date=datetime.fromtimestamp(0, timezone.utc)
        )

        # Create RemoteApp
        RemoteApp.objects.create(
            repo=remote_repository,
            last_updated_date=datetime.fromtimestamp(0, timezone.utc)
        )

    def tearDown(self):
        shutil.rmtree(TEST_DIR)

    def test_str(self):
        self.assertEqual('org.example 0 test.apk', str(self.apk))

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

    @patch('requests.get')
    def test_failed_download(self, get):
        # remove file and assert that it is gone
        self.apk.file.delete()
        self.assertFalse(self.apk.file)

        # fake return value of GET request
        get.return_value = requests.Response()
        get.return_value.status_code = 404

        # try to download file and assert an excetion was raised
        with self.assertRaises(requests.exceptions.HTTPError):
            self.apk.download('url/download.apk')

    @patch('requests.get')
    def test_download_only_when_file_missing(self, get):
        # try to download file and assert there was no GET request (because it already exists)
        self.apk.download('url/download.apk')
        self.assertFalse(get.called)

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
        added = datetime.fromtimestamp(package_info['added'] / 1000, timezone.utc)
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


@override_settings(MEDIA_ROOT=TEST_DIR, PRIVATE_REPO_ROOT=TEST_PRIVATE_DIR)
class ApkPointerTestCase(TestCase):
    apk_file_name = 'test_1.apk'

    def setUp(self):
        # Create Repository
        self.repo = Repository.objects.create(user=User.objects.create(username='user2'))

        # Create ApkPointer
        self.apk_pointer = ApkPointer(repo=self.repo)

        # Attach a real APK file to the pointer
        file_path = os.path.join(TEST_FILES_DIR, self.apk_file_name)
        with open(file_path, 'rb') as f:
            self.apk_pointer.file.save(self.apk_file_name, File(f), save=True)

    def tearDown(self):
        shutil.rmtree(TEST_DIR)

    def test_str(self):
        self.apk_pointer.app = App.objects.create(repo=self.repo, name='TestApp')
        self.apk_pointer.apk = Apk.objects.create()
        self.assertEqual('TestApp - 0 - user_2/repo_1/repo/test_1.apk', str(self.apk_pointer))

    def test_initialize_rejects_invalid_apk(self):
        # overwrite APK file with rubbish
        self.apk_pointer.file.delete()
        self.apk_pointer.file.save(self.apk_file_name, BytesIO(b'foo'), save=True)

        # initialize the pointer and expect a ValidationError
        with self.assertRaises(ValidationError):
            self.apk_pointer.initialize()

    @patch('fdroidserver.update.scan_apk')
    def test_initialize_rejects_invalid_apk_scan(self, scan_apk):
        scan_apk.return_value = True, None, None  # scan tells us to skip this APK

        # initialize the pointer and expect a ValidationError
        with self.assertRaises(ValidationError):
            self.apk_pointer.initialize()

    def test_initialize(self):
        # create the repository environment
        fake_repo_create(self.apk_pointer.repo)

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
        fake_repo_create(self.apk_pointer.repo)

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
        fake_repo_create(self.apk_pointer.repo)

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

    def test_icons_get_deleted_from_repo(self):
        # create the repository environment
        fake_repo_create(self.apk_pointer.repo)

        # initialize the ApkPointer with its stored APK file
        self.apk_pointer.initialize()

        # Get icon name
        icon_name = \
            self.apk_pointer.apk.package_id + "." + str(self.apk_pointer.apk.version_code) + ".png"

        # Get path of repository
        path = self.apk_pointer.repo.get_repo_path()

        # List with icon directories
        for icon_directory in get_all_icon_dirs(path):
            icon = os.path.join(icon_directory, icon_name)
            # Check that icons exist
            self.assertTrue(os.path.isfile(icon))

        # Delete app icons
        self.apk_pointer.delete()

        for icon_directory in get_all_icon_dirs(path):
            icon = os.path.join(icon_directory, icon_name)
            # Check that icons do not exist
            self.assertFalse(os.path.isfile(icon))

    def test_link_file_from_apk(self):
        # delete pointer file and add one for apk
        self.apk_pointer.file.delete()
        self.apk_pointer.apk = Apk.objects.create()
        self.apk_pointer.apk.file.save('test.apk', BytesIO(b'foo'), save=True)

        # link pointer file from apk
        self.assertFalse(self.apk_pointer.file)
        self.apk_pointer.link_file_from_apk()
        self.assertTrue(self.apk_pointer.file)
        self.assertTrue(os.path.isfile(self.apk_pointer.file.path))

    def test_link_file_from_apk_only_when_no_file(self):
        file_path = self.apk_pointer.file.path
        self.assertTrue(os.path.isfile(file_path))

        self.apk_pointer.link_file_from_apk()  # linking should bail out, because file exists

        self.assertEqual(file_path, self.apk_pointer.file.path)


class RemoteApkPointerTestCase(TestCase):

    def setUp(self):
        self.repo = RemoteRepository.objects.get(pk=1)
        self.apk = Apk.objects.create(package_id='org.example', version_code=1337)
        date = datetime.fromtimestamp(0, timezone.utc)
        self.app = RemoteApp.objects.create(repo=self.repo, package_id='org.example',
                                            name='TestApp', last_updated_date=date)
        self.remote_apk_pointer = RemoteApkPointer.objects.create(apk=self.apk, app=self.app,
                                                                  url='test_url/test.apk')

    def test_str(self):
        self.assertEqual('TestApp - 1337 - test.apk', str(self.remote_apk_pointer))

    def test_pointer_check_when_deleted(self):
        self.assertTrue(Apk.objects.all().exists())
        self.remote_apk_pointer.delete()
        self.assertFalse(Apk.objects.all().exists())  # Apk got deleted, because no more pointers
