import os
import shutil

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from maker import DEFAULT_USER_NAME
from maker.models import App, Apk, ApkPointer, Repository
from .. import TEST_FILES_DIR, TEST_DIR, TEST_MEDIA_DIR


@override_settings(MEDIA_ROOT=TEST_MEDIA_DIR)
class ApkViewTestCase(TestCase):

    def setUp(self):
        self.repo = Repository.objects.create(
            name="Test Name",
            description="Test Description",
            url="https://example.org",
            user=User.objects.get(username=DEFAULT_USER_NAME),
        )
        self.repo.chdir()

    def tearDown(self):
        if os.path.isdir(TEST_DIR):
            shutil.rmtree(TEST_DIR)

    def test_apk_upload(self):
        self.upload_file('test_1.apk')

    def test_non_apk_upload(self):
        self.upload_file('test.avi')

    def test_upload_multiple_apks(self):
        self.upload_files(['test_1.apk', 'test_2.apk'])
        self.assertEqual(1, App.objects.all().count())

    def test_upload_multiple_non_apks(self):
        self.upload_files(['test.ods', 'test.pdf'])
        self.assertEqual(1, App.objects.all().count())

    def test_upload_multiple_apks_and_non_apks(self):
        self.upload_files(['test_1.apk', 'test.pdf'])
        self.assertEqual(2, App.objects.all().count())

    def upload_file(self, filename):
        self.assertEqual(0, App.objects.all().count())
        self.assertEqual(0, Apk.objects.all().count())
        self.assertEqual(0, ApkPointer.objects.all().count())

        with open(os.path.join(TEST_FILES_DIR, filename), 'rb') as f:
            self.client.post(reverse('apk_upload', kwargs={'repo_id': self.repo.id}), {'apks': f})

        self.assertEqual(1, App.objects.all().count())
        self.assertEqual(1, Apk.objects.all().count())
        self.assertEqual(1, ApkPointer.objects.all().count())

    def upload_files(self, files):
        self.assertEqual(0, App.objects.all().count())
        self.assertEqual(0, Apk.objects.all().count())
        self.assertEqual(0, ApkPointer.objects.all().count())

        # open all files
        apks = []
        for filename in files:
            apks.append(open(os.path.join(TEST_FILES_DIR, filename), 'rb'))

        # post all files and ensure they are closed again afterwards
        try:
            self.client.post(reverse('apk_upload', kwargs={'repo_id': self.repo.id}),
                             {'apks': apks})
        finally:
            for f in apks:
                f.close()

        self.assertEqual(len(files), Apk.objects.all().count())
        self.assertEqual(len(files), ApkPointer.objects.all().count())

    def test_delete_apk(self):
        # create required objects
        app = App.objects.create(repo=self.repo, package_id='org.example', name='AppName')
        app.default_translate()
        app.save()
        apk = Apk.objects.create(package_id=app.package_id, version_code=1337,
                                 version_name='VersionName')
        apk_pointer = ApkPointer.objects.create(repo=self.repo, app=app, apk=apk)

        # request APK deletion confirmation page
        kwargs = {'repo_id': self.repo.id, 'app_id': app.id, 'pk': apk_pointer.id}
        response = self.client.get(reverse('apk_delete', kwargs=kwargs))

        # assert that it contains the relevant information
        self.assertContains(response, app.name)
        self.assertContains(response, apk.version_name)
        self.assertContains(response, apk.version_code)

        # request the APK pointer to be deleted
        response = self.client.post(reverse('apk_delete', kwargs=kwargs))
        self.assertRedirects(response, app.get_edit_url())

        # assert that the pointer and the APK (because it had no other pointers) got deleted
        self.assertEqual(0, Apk.objects.all().count())
        self.assertEqual(0, ApkPointer.objects.all().count())
