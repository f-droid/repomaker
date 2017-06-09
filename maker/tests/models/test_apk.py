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

import maker.models.app
from maker.models import Apk, ApkPointer, RemoteApkPointer, App, RemoteApp, RemoteRepository, \
    Repository
from maker.storage import get_apk_file_path
from .. import TEST_DIR, TEST_FILES_DIR, TEST_PRIVATE_DIR, datetime_is_recent, fake_repo_create


@override_settings(MEDIA_ROOT=TEST_DIR)
class ApkTestCase(TestCase):

    def setUp(self):
        # Create APK
        self.apk = Apk.objects.create()
        # Attach a real APK file
        self.apk_file_name = 'test.apk'
        file_path = os.path.join(TEST_FILES_DIR, 'test_1.apk')
        with open(file_path, 'rb') as f:
            self.apk.file.save(self.apk_file_name, File(f), save=True)

        # Create Repository
        self.repo = Repository.objects.create(name="Test", description="Test",
                                              url="https://f-droid.org",
                                              user=User.objects.create(username='user2'))

        # Create RemoteRepository
        self.remote_repository = RemoteRepository.objects.create(
            name='Test',
            description='Test',
            url='https://f-droid.org',
            last_change_date=datetime.fromtimestamp(0, timezone.utc)
        )

        # Create RemoteApp
        self.remote_app = RemoteApp.objects.create(
            repo=self.remote_repository,
            last_updated_date=datetime.fromtimestamp(0, timezone.utc)
        )

    def tearDown(self):
        shutil.rmtree(TEST_DIR)

    def test_str(self):
        self.apk.package_id = 'org.example'
        self.assertEqual('org.example 0 packages/test.apk', str(self.apk))

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

        # fake return value of GET request for APK
        get.return_value.status_code = requests.codes.ok
        with open(os.path.join(TEST_FILES_DIR, 'test_1.apk'), 'rb') as f:
            get.return_value.content = f.read()

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
    def test_download_404(self, get):
        # remove file and assert that it is gone
        self.apk.file.delete()
        self.assertFalse(self.apk.file)

        # fake return value of GET request
        get.return_value = requests.Response()
        get.return_value.status_code = 404

        # try to download file and assert an exception was raised
        with self.assertRaises(requests.exceptions.HTTPError):
            self.apk.download('url/download.apk')

    @patch('requests.get')
    def test_download_invalid_apk(self, get):
        # remove file and assert that it is gone
        self.apk.file.delete()
        self.assertFalse(self.apk.file)

        # create an ApkPointer pointing to the Apk
        ApkPointer.objects.create(repo=self.repo, apk=self.apk)
        RemoteApkPointer.objects.create(app=self.remote_app, apk=self.apk)
        self.assertEqual(1, ApkPointer.objects.all().count())
        self.assertEqual(1, RemoteApkPointer.objects.all().count())

        # fake return value of GET request
        get.return_value.status_code = requests.codes.ok
        get.return_value.content = b'foo'

        # try to download the invalid file
        self.apk.download('url/download.apk')

        # assert that Apk and ApkPointer got deleted
        self.assertEqual(0, Apk.objects.all().count())
        self.assertEqual(0, ApkPointer.objects.all().count())
        self.assertEqual(0, RemoteApkPointer.objects.all().count())

    @patch('requests.get')
    def test_download_apk_with_invalid_signature(self, get):
        # remove file and assert that it is gone
        self.apk.file.delete()
        self.assertFalse(self.apk.file)

        # create an ApkPointer pointing to the Apk
        ApkPointer.objects.create(repo=self.repo, apk=self.apk)
        RemoteApkPointer.objects.create(app=self.remote_app, apk=self.apk)
        self.assertEqual(1, ApkPointer.objects.all().count())
        self.assertEqual(1, RemoteApkPointer.objects.all().count())

        # fake return value of GET request for APK
        get.return_value.status_code = requests.codes.ok
        with open(os.path.join(TEST_FILES_DIR, 'test_invalid_signature.apk'), 'rb') as f:
            get.return_value.content = f.read()

        # try to download the invalid file
        self.apk.download('url/download.apk')

        # assert that Apk and ApkPointer got deleted
        self.assertEqual(0, Apk.objects.all().count())
        self.assertEqual(0, ApkPointer.objects.all().count())
        self.assertEqual(0, RemoteApkPointer.objects.all().count())

    @patch('requests.get')
    def test_download_only_when_file_missing(self, get):
        # try to download file and assert there was no GET request (because it already exists)
        self.apk.download('url/download.apk')
        self.assertFalse(get.called)

    @patch('requests.get')
    def test_download_non_apk(self, get):
        # remove file and assert that it is gone
        self.apk.file.delete()
        self.assertFalse(self.apk.file)

        # create ApkPointer and assert it doesn't have a file
        apk_pointer = ApkPointer.objects.create(apk=self.apk, repo=Repository.objects.get(id=1))
        self.assertFalse(apk_pointer.file)

        # fake return value of GET request for APK
        get.return_value.status_code = requests.codes.ok
        with open(os.path.join(TEST_FILES_DIR, 'test_1.apk'), 'rb') as f:
            get.return_value.content = f.read()

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

    def test_initialize(self):
        # initialize the Apk with its stored APK file
        self.apk.initialize()

        # assert that it has been initialized properly
        apk = self.apk
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

    def test_initialize_rejects_invalid_apk(self):
        # overwrite APK file with rubbish
        self.apk.file.delete()
        self.apk.file.save(self.apk_file_name, BytesIO(b'foo'), save=True)
        with self.assertRaises(ValidationError):
            self.apk.initialize()

    @patch('fdroidserver.update.scan_apk_aapt')
    def test_initialize_rejects_invalid_apk_scan(self, scan_apk):
        scan_apk.return_value = None
        with self.assertRaises(ValidationError):
            self.apk.initialize()

    def test_initialize_reuses_existing_apk(self):
        # create existing Apk object with same package_id and hash
        apk = Apk(package_id='org.bitbucket.tickytacky.mirrormirror',
                  hash='64021f6d632eb5ba55bdeb5c4a78ed612bd3facc25d9a8a5d1c9d5d7a6bcc047')
        apk.save()

        # initialize the Apk with its stored APK file
        self.apk.initialize()

        # assert that the Apk object was deleted in favor of the existing one
        self.assertEqual(1, Apk.objects.count())
        self.assertFalse(self.apk.file)
        self.assertFalse(Apk.objects.filter(pk=self.apk.pk).exists())

    def test_initialize_non_apk(self):
        # overwrite APK file with image file
        self.replace_apk_file(os.path.join(TEST_FILES_DIR, 'test.png'), 'test.png')

        # initialize the ApkPointer with its stored image file
        self.apk.initialize()

        # assert that image was added properly
        self.assertEqual('test', self.apk.package_id)
        self.assertEqual(10, len(str(self.apk.version_code)))
        self.assertEqual(datetime.now().strftime('%Y-%m-%d'), self.apk.version_name)
        self.assertEqual(11575, self.apk.size)
        self.assertEqual('9b6acf7fa93477170b222bea2d0395fda2557f2ce953f138b011825f333ff02c',
                         self.apk.hash)
        self.assertEqual('sha256', self.apk.hash_type)

    def test_initialize_standard_file_name(self):
        # overwrite APK file with image that has standard file name
        self.replace_apk_file(os.path.join(TEST_FILES_DIR, 'test.png'), 'package_name_1337.png')

        # initialize the ApkPointer with its stored image file
        self.apk.initialize()

        # assert that version and package name were extracted properly from filename
        self.assertEqual('package_name', self.apk.package_id)
        self.assertEqual(1337, self.apk.version_code)
        self.assertEqual('1337', self.apk.version_name)

    def test_initialize_no_file_extension(self):
        # overwrite APK file with image that has no file extension
        self.replace_apk_file(os.path.join(TEST_FILES_DIR, 'test.png'), 'test')
        self.assertEqual('test', os.path.basename(self.apk.file.name))

        # initialize the Apk with its stored image file
        self.apk.initialize()

        # assert that package name was extracted properly from filename
        self.assertEqual('test', self.apk.package_id)

    def test_initialize_videos(self):
        # initialize the Apk with video file
        self.replace_apk_file(os.path.join(TEST_FILES_DIR, 'test.avi'), 'test1.avi')
        self.apk.initialize(self.repo)
        # assert that video type was recognized
        self.assertEqual(maker.models.app.VIDEO, App.objects.get(package_id='test1').type)

        # initialize the Apk with video file
        self.replace_apk_file(os.path.join(TEST_FILES_DIR, 'test.mp4'), 'test2.mp4')
        self.apk.initialize(self.repo)
        # assert that video type was recognized
        self.assertEqual(maker.models.app.VIDEO, App.objects.get(package_id='test2').type)

        # initialize the Apk with video file
        self.replace_apk_file(os.path.join(TEST_FILES_DIR, 'test.webm'), 'test3.webm')
        self.apk.initialize(self.repo)
        # assert that video type was recognized
        self.assertEqual(maker.models.app.VIDEO, App.objects.get(package_id='test3').type)

    def test_initialize_audios(self):
        # initialize the Apk with audio file
        self.replace_apk_file(os.path.join(TEST_FILES_DIR, 'test.flac'), 'test1.flac')
        self.apk.initialize(self.repo)
        # assert that audio type was recognized
        self.assertEqual(maker.models.app.AUDIO, App.objects.get(package_id='test1').type)

        # initialize the Apk with audio file
        self.replace_apk_file(os.path.join(TEST_FILES_DIR, 'test.mp3'), 'test2.mp3')
        self.apk.initialize(self.repo)
        # assert that audio type was recognized
        self.assertEqual(maker.models.app.AUDIO, App.objects.get(package_id='test2').type)

        # initialize the Apk with audio file
        self.replace_apk_file(os.path.join(TEST_FILES_DIR, 'test.ogg'), 'test3.ogg')
        self.apk.initialize(self.repo)
        # assert that audio type was recognized
        self.assertEqual(maker.models.app.AUDIO, App.objects.get(package_id='test3').type)

    def test_initialize_books(self):
        # initialize the Apk with book file
        self.replace_apk_file(os.path.join(TEST_FILES_DIR, 'test.epub'), 'test1.epub')
        self.apk.initialize(self.repo)
        # assert that book type was recognized
        self.assertEqual(maker.models.app.BOOK, App.objects.get(package_id='test1').type)

        # initialize the Apk with book file
        self.replace_apk_file(os.path.join(TEST_FILES_DIR, 'test.mobi'), 'test2.mobi')
        self.apk.initialize(self.repo)
        # assert that book type was recognized
        self.assertEqual(maker.models.app.BOOK, App.objects.get(package_id='test2').type)

    def test_initialize_documents(self):
        # initialize the Apk with document file
        self.replace_apk_file(os.path.join(TEST_FILES_DIR, 'test.docx'), 'test1.docx')
        self.apk.initialize(self.repo)
        # assert that document type was recognized
        self.assertEqual(maker.models.app.DOCUMENT, App.objects.get(package_id='test1').type)

        # initialize the Apk with document file
        self.replace_apk_file(os.path.join(TEST_FILES_DIR, 'test.odt'), 'test2.odt')
        self.apk.initialize(self.repo)
        # assert that document type was recognized
        self.assertEqual(maker.models.app.DOCUMENT, App.objects.get(package_id='test2').type)

        # initialize the Apk with document file
        self.replace_apk_file(os.path.join(TEST_FILES_DIR, 'test.ods'), 'test3.ods')
        self.apk.initialize(self.repo)
        # assert that document type was recognized
        self.assertEqual(maker.models.app.DOCUMENT, App.objects.get(package_id='test3').type)

        # initialize the Apk with document file
        self.replace_apk_file(os.path.join(TEST_FILES_DIR, 'test.pdf'), 'test4.pdf')
        self.apk.initialize(self.repo)
        # assert that document type was recognized
        self.assertEqual(maker.models.app.DOCUMENT, App.objects.get(package_id='test4').type)

    def test_initialize_unsupported_type(self):
        self.replace_apk_file(os.path.join(TEST_FILES_DIR, 'keystore.jks'), 'test.php')
        with self.assertRaises(ValidationError):
            self.apk.initialize()

        self.replace_apk_file(os.path.join(TEST_FILES_DIR, 'keystore.jks'), 'test.py')
        with self.assertRaises(ValidationError):
            self.apk.initialize()

        self.replace_apk_file(os.path.join(TEST_FILES_DIR, 'keystore.jks'), 'test.pl')
        with self.assertRaises(ValidationError):
            self.apk.initialize()

        self.replace_apk_file(os.path.join(TEST_FILES_DIR, 'keystore.jks'), 'test.cgi')
        with self.assertRaises(ValidationError):
            self.apk.initialize()

    def test_apply_json_package_info(self):
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
        apk = Apk()
        apk.apply_json_package_info(package_info)
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
        path = self.apk.file.path
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(self.apk.file.name, 'packages/test.apk')

        # delete APK and assert that file got deleted as well
        self.apk.delete()
        self.assertFalse(os.path.isfile(path))

    def test_apk_gets_deleted_without_pointers(self):
        # Delete APK and assert that it got deleted
        self.apk.delete_if_no_pointers()
        self.assertFalse(Apk.objects.filter(package_id="org.example").exists())

    def test_apk_does_not_get_deleted_with_pointer(self):
        # Create local pointer
        apk_pointer = ApkPointer(apk=self.apk, repo=Repository.objects.get(id=1))
        apk_pointer.save()

        # Delete APK and assert that it did not get deleted
        self.apk.package_id = 'org.example'
        self.apk.save()
        self.apk.delete_if_no_pointers()
        self.assertTrue(Apk.objects.filter(package_id='org.example').exists())

    def test_apk_does_not_get_deleted_with_remote_pointer(self):
        # Create remote pointer
        remote_apk_pointer = RemoteApkPointer(apk=self.apk, app=RemoteApp.objects.get(id=1))
        remote_apk_pointer.save()

        # Delete APK and assert that it did not get deleted
        self.apk.package_id = 'org.example'
        self.apk.save()
        self.apk.delete_if_no_pointers()
        self.assertTrue(Apk.objects.filter(package_id="org.example").exists())

    def replace_apk_file(self, file_path, file_name):
        """
        Overwrites this test's Apk file with the given file_path.
        :param file_path: The absolute path to the file to be used.
        :param file_name: The new filename of the saved file.
        """
        self.apk.file.delete()
        self.apk.package_id = ''  # also reset package_id
        with open(file_path, 'rb') as f:
            self.apk.file.save(file_name, File(f), save=True)


@override_settings(MEDIA_ROOT=TEST_DIR, PRIVATE_REPO_ROOT=TEST_PRIVATE_DIR)
class ApkPointerTestCase(TestCase):
    apk_file_name = 'test_1.apk'

    def setUp(self):
        # Create Repository
        self.repo = Repository.objects.create(user=User.objects.create(username='user2'))

        # Create APK
        self.apk = Apk.objects.create()

        # Attach a real APK file to the Apk
        file_path = os.path.join(TEST_FILES_DIR, self.apk_file_name)
        with open(file_path, 'rb') as f:
            self.apk.file.save(self.apk_file_name, File(f), save=True)

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

    def test_initialize(self):
        self.apk.initialize(self.repo)  # this calls self.apk_pointer.initialize()

        # assert that global APK file has been linked/copied properly
        self.assertEqual(get_apk_file_path(self.apk, self.apk_file_name), self.apk.file.name)
        self.assertTrue(os.path.isfile(os.path.join(settings.MEDIA_ROOT, self.apk.file.name)))

        # get the created Apk object and assert that it has been created properly
        app = App.objects.get(pk=1)
        self.assertEqual(self.apk_pointer.repo, app.repo)
        self.assertEqual(self.apk.package_id, app.package_id)
        self.assertEqual(app.package_id, app.name)  # this apk has no name, so use fallback

        # assert that the app icon has been created properly
        icon_name = app.package_id + '.' + str(self.apk.version_code) + '.png'
        self.assertTrue(app.icon.name.endswith(icon_name))
        self.assertTrue(os.path.isfile(app.icon.path))

    def test_initialize_reuses_existing_app(self):
        # create existing App object with same repo and package_id
        app = App.objects.create(repo=self.apk_pointer.repo,
                                 package_id='org.bitbucket.tickytacky.mirrormirror')

        # initialize the ApkPointer with its stored APK file
        self.apk.package_id = app.package_id
        self.apk_pointer.apk = self.apk
        self.apk_pointer.initialize({'type': 'apk', 'name': app.package_id, 'icons_src': {}})

        # assert that the App object was re-used
        self.assertTrue(len(App.objects.all()) == 1)
        self.assertEqual(app, self.apk_pointer.app)

        # assert that existing App object was updated
        app = App.objects.get(pk=app.pk)
        self.assertEqual('org.bitbucket.tickytacky.mirrormirror', app.name)
        self.assertTrue(app.icon)

    def test_initialize_non_apk(self):
        # overwrite APK file with image file
        self.apk.file.delete()
        file_path = os.path.join(TEST_FILES_DIR, 'test.png')
        with open(file_path, 'rb') as f:
            self.apk.file.save('test.png', File(f), save=True)

        # initialize the ApkPointer with its stored image file
        self.apk.initialize(self.repo)  # this calls self.apk_pointer.initialize()

        # assert that image was added properly
        self.assertEqual('test', self.apk.package_id)
        self.assertEqual(10, len(str(self.apk.version_code)))
        self.assertEqual(datetime.now().strftime('%Y-%m-%d'), self.apk.version_name)
        self.assertEqual(11575, self.apk.size)
        self.assertEqual('9b6acf7fa93477170b222bea2d0395fda2557f2ce953f138b011825f333ff02c',
                         self.apk.hash)
        self.assertEqual('sha256', self.apk.hash_type)

        # assert that image "app" was added properly
        apps = App.objects.all()
        self.assertEqual(1, apps.count())
        self.assertEqual(apps[0], ApkPointer.objects.get(apk=self.apk).app)  # pointer app
        self.assertEqual('test', apps[0].name)  # name
        self.assertEqual('test', apps[0].package_id)  # package ID
        self.assertEqual(maker.models.app.IMAGE, apps[0].type)  # app type
        self.assertEqual(settings.APP_DEFAULT_ICON, apps[0].icon.name)  # icon

    def test_icons_get_deleted_from_repo(self):
        # create the repository environment
        fake_repo_create(self.apk_pointer.repo)
        self.apk_pointer.apk = self.apk
        self.apk_pointer.apk.version_code = 1137

        # List with icon directories
        icon_name = \
            self.apk_pointer.apk.package_id + "." + str(self.apk_pointer.apk.version_code) + ".png"
        for icon_directory in get_all_icon_dirs(self.repo.get_repo_path()):
            icon = os.path.join(icon_directory, icon_name)
            with open(icon, 'wb') as f:
                f.write(b'foo')
            # Check that icons exist
            self.assertTrue(os.path.isfile(icon))

        # Delete app icons
        self.apk_pointer.delete()

        for icon_directory in get_all_icon_dirs(self.repo.get_repo_path()):
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
