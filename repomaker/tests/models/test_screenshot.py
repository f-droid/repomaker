import io
import os
import shutil
from datetime import datetime, timezone
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from repomaker.models import Repository, RemoteRepository, App, RemoteApp, Screenshot, \
    RemoteScreenshot
from repomaker.models.screenshot import AbstractScreenshot, PHONE, SEVEN_INCH, TEN_INCH, TV, WEAR
from repomaker.storage import get_screenshot_file_path

from .. import RmTestCase


class AbstractScreenshotTestCase(TestCase):

    def test_get_url(self):  # for getting screenshot coverage to 100%
        with self.assertRaises(NotImplementedError):
            AbstractScreenshot().get_url()


class ScreenshotTestCase(RmTestCase):

    def setUp(self):
        super().setUp()
        self.app = App.objects.create(repo=self.repo, name='TestApp', package_id='org.example')
        self.screenshot = Screenshot.objects.create(app=self.app, language_code='en-us')

    def test_str(self):
        self.assertTrue(self.app.name in str(self.screenshot))
        self.assertTrue(self.screenshot.type in str(self.screenshot))
        self.assertTrue(self.screenshot.language_code in str(self.screenshot))

    def test_get_relative_path(self):
        self.assertEqual('org.example/en-US/phoneScreenshots', self.screenshot.get_relative_path())

    def test_file(self):
        self.screenshot.file.save('test.png', io.BytesIO(b'foo'))
        self.assertTrue(os.path.isfile(self.screenshot.file.path))

    def test_get_url(self):
        self.test_file()  # needs to save a file first, because getting URL that includes file
        self.assertEqual('/media/user_1/repo_1/repo/org.example/en-US/phoneScreenshots/test.png',
                         self.screenshot.get_url())

    def test_types(self):
        Screenshot.objects.create(app=self.app, type=PHONE)
        Screenshot.objects.create(app=self.app, type=SEVEN_INCH)
        Screenshot.objects.create(app=self.app, type=TEN_INCH)
        Screenshot.objects.create(app=self.app, type=TV)
        Screenshot.objects.create(app=self.app, type=WEAR)

    def test_languages(self):
        Screenshot.objects.create(app=self.app, language_code='en')
        Screenshot.objects.create(app=self.app, language_code='es')
        Screenshot.objects.create(app=self.app, language_code='de')

    def test_file_deletion(self):
        self.test_file()  # add a file to local Screenshot
        file_path = self.screenshot.file.path
        self.assertTrue(os.path.isfile(file_path))

        # delete screenshot and assert that file was deleted as well
        self.screenshot.delete()
        self.assertFalse(os.path.isfile(file_path))


class RemoteScreenshotTestCase(TestCase):

    def setUp(self):
        # remote objects
        self.remote_repo = RemoteRepository.objects.get(pk=1)
        date = datetime.fromtimestamp(1337, timezone.utc)
        self.remote_app = RemoteApp.objects.create(repo=self.remote_repo, name='TestApp',
                                                   package_id='org.example', last_updated_date=date)
        self.remote_screenshot = RemoteScreenshot.objects.create(app=self.remote_app,
                                                                 url='test_url/test.png')

        # local objects
        self.user = User.objects.create(username='user2')
        self.repo = Repository.objects.create(user=self.user)
        self.app = App.objects.create(repo=self.repo, package_id='org.example')

    def tearDown(self):
        if os.path.isdir(settings.TEST_DIR):
            shutil.rmtree(settings.TEST_DIR)

    def test_str(self):
        self.assertTrue(self.remote_app.name in str(self.remote_screenshot))
        self.assertTrue(self.remote_screenshot.type in str(self.remote_screenshot))
        self.assertTrue(self.remote_screenshot.language_code in str(self.remote_screenshot))
        self.assertTrue('test.png' in str(self.remote_screenshot))

    def test_get_url(self):
        self.assertEqual('test_url/test.png', self.remote_screenshot.get_url())

    def test_add(self):
        # add to remote screenshots from RemoteApp
        RemoteScreenshot.add('en', PHONE, self.remote_app, 'base_url/', ['test1.png', 'test2.png'])

        # assert both screenshots have been added properly
        remote_screenshots = RemoteScreenshot.objects.all()
        self.assertEqual(1+2, len(remote_screenshots))
        for screenshot in remote_screenshots:
            if screenshot == self.remote_screenshot:
                continue
            self.assertEqual(self.remote_app, screenshot.app)
            self.assertEqual('en', screenshot.language_code)
            self.assertEqual(PHONE, screenshot.type)
            self.assertTrue(screenshot.url == 'base_url/test1.png' or
                            screenshot.url == 'base_url/test2.png')

    def test_add_with_unsupported_type(self):
        # add RemoteScreenshot with unsupported type
        RemoteScreenshot.add('en', 'unsupported', self.remote_app, 'base_url/', ['test1.png'])

        # assert that no more RemoteScreenshots have been created
        self.assertEqual(1, RemoteScreenshot.objects.all().count())

    @patch('repomaker.tasks.download_remote_screenshot')
    def test_download_async(self, download_remote_screenshot):
        # schedule async download
        self.remote_screenshot.download_async(self.app)
        download_remote_screenshot.assert_called_once_with(self.remote_screenshot.pk, self.app.pk)

    @patch('requests.get')
    def test_download(self, get):
        # do a fake screenshot download
        get.return_value.status_code = 200
        get.return_value.content = b'foo'
        self.remote_screenshot.download(self.app.pk)
        get.assert_called_once_with('test_url/test.png')

        # exactly one Screenshot was created
        self.assertEqual(1, Screenshot.objects.all().count())

        # assert that local Screenshot was created properly
        screenshot = Screenshot.objects.get(pk=1)
        self.assertEqual(self.app, screenshot.app)
        self.assertEqual(self.remote_screenshot.type, screenshot.type)
        self.assertEqual(self.remote_screenshot.language_code, screenshot.language_code)
        self.assertEqual(get_screenshot_file_path(screenshot, 'test.png'), screenshot.file.name)
        os.path.isfile(screenshot.file.path)

    @patch('requests.get')
    def test_failed_download(self, get):
        # do a fake screenshot download
        get.return_value.status_code = 404
        self.remote_screenshot.download(self.app.pk)

        # no Screenshot was created
        self.assertEqual(0, Screenshot.objects.all().count())
