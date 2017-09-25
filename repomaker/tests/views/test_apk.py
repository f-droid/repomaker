import os

from django.conf import settings
from django.urls import reverse
from repomaker.models import App, Apk, ApkPointer

from .. import RmTestCase


class ApkViewTestCase(RmTestCase):

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

        with open(os.path.join(settings.TEST_FILES_DIR, filename), 'rb') as f:
            self.client.post(reverse('apk_upload', kwargs={'repo_id': self.repo.id}), {'apks': f})

        self.assertEqual(1, App.objects.all().count())
        self.assertEqual(1, Apk.objects.all().count())
        self.assertEqual(1, ApkPointer.objects.all().count())

    def test_apk_upload_reuses_existing(self):
        Apk.objects.create(package_id='org.bitbucket.tickytacky.mirrormirror',
                           hash='7733e133eec140ab5e410f69955a4cba4a61133437ba436e92b75f03cbabfd52')

        with open(os.path.join(settings.TEST_FILES_DIR, 'test_1.apk'), 'rb') as f:
            self.client.post(reverse('apk_upload', kwargs={'repo_id': self.repo.id}), {'apks': f})

        self.assertEqual(1, App.objects.all().count())
        self.assertEqual(1, Apk.objects.all().count())
        self.assertEqual(1, ApkPointer.objects.all().count())

        apk = Apk.objects.get()
        self.assertTrue(apk.file)
        self.assertEqual('packages/test_1.apk', apk.file.name)
        self.assertEqual(apk, ApkPointer.objects.get().apk)

    def test_upload_invalid_apk(self):
        with open(os.path.join(settings.TEST_FILES_DIR, 'test_invalid_signature.apk'), 'rb') as f:
            response = self.client.post(reverse('apk_upload', kwargs={'repo_id': self.repo.id}),
                                        {'apks': f})
        self.assertContains(response, 'Error')
        self.assertContains(response, 'Invalid APK signature')

    def upload_files(self, files):
        self.assertEqual(0, App.objects.all().count())
        self.assertEqual(0, Apk.objects.all().count())
        self.assertEqual(0, ApkPointer.objects.all().count())

        # open all files
        apks = []
        for filename in files:
            apks.append(open(os.path.join(settings.TEST_FILES_DIR, filename), 'rb'))

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
