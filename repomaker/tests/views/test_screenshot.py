import os
import shutil

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from repomaker import DEFAULT_USER_NAME
from repomaker.models import App, Repository, Screenshot
from .. import TEST_DIR, TEST_MEDIA_DIR


@override_settings(MEDIA_ROOT=TEST_MEDIA_DIR)
class ScreenshotViewTestCase(TestCase):

    def setUp(self):
        self.repo = Repository.objects.create(
            name="Test Name",
            description="Test Description",
            url="https://example.org",
            user=User.objects.get(username=DEFAULT_USER_NAME),
        )
        self.repo.chdir()

        self.app = App.objects.create(
            repo=self.repo,
            package_id='org.example',
            name='AppName',
        )
        self.app.default_translate()
        self.app.save()

    def tearDown(self):
        if os.path.isdir(TEST_DIR):
            shutil.rmtree(TEST_DIR)

    def test_delete_screenshot(self):
        screenshot = Screenshot.objects.create(app=self.app, file='test.png')

        # request screenshot deletion confirmation page
        kwargs = {'repo_id': self.repo.id, 'app_id': self.app.id, 's_id': screenshot.id}
        response = self.client.get(reverse('screenshot_delete', kwargs=kwargs))

        # assert that it contains the relevant information
        self.assertContains(response, self.app.name)
        self.assertContains(response, screenshot.file.url)

        # request the screenshot to be deleted
        response = self.client.post(reverse('screenshot_delete', kwargs=kwargs))
        self.assertRedirects(response, self.app.get_edit_url())

        # assert that the pointer got deleted
        self.assertEqual(0, Screenshot.objects.all().count())
