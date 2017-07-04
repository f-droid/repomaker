import os
import shutil

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from maker import DEFAULT_USER_NAME
from maker.models import App, Apk, ApkPointer, Repository, Screenshot
from .. import TEST_DIR, TEST_MEDIA_DIR, TEST_FILES_DIR


@override_settings(MEDIA_ROOT=TEST_MEDIA_DIR)
class AppViewTestCase(TestCase):

    def setUp(self):
        # create repository for singe-user-mode
        self.repo = Repository.objects.create(
            name="Test Name",
            description="Test Description",
            url="https://example.org",
            user=User.objects.get(username=DEFAULT_USER_NAME),
        )
        self.repo.chdir()

        # create app in repo
        self.app = App.objects.create(repo=self.repo,
                                      package_id='org.bitbucket.tickytacky.mirrormirror',
                                      name='TestApp', summary='TestSummary', description='TestDesc',
                                      website='TestSite', author_name='author')

        self.edit_app_url = reverse('edit_app',
                                    kwargs={'repo_id': self.repo.id, 'app_id': self.app.id})

    def tearDown(self):
        if os.path.isdir(TEST_DIR):
            shutil.rmtree(TEST_DIR)

    def test_upload_apk_and_update(self):
        self.assertEqual(1, App.objects.all().count())
        self.assertEqual(0, Apk.objects.all().count())
        self.assertEqual(0, ApkPointer.objects.all().count())

        with open(os.path.join(TEST_FILES_DIR, 'test_1.apk'), 'rb') as f:
            self.client.post(self.edit_app_url, {'apks': f})

        self.assertEqual(1, App.objects.all().count())
        self.assertEqual(1, Apk.objects.all().count())
        self.assertEqual(1, ApkPointer.objects.all().count())
        self.assertEqual(1, self.app.apkpointer_set.count())

        with open(os.path.join(TEST_FILES_DIR, 'test_2.apk'), 'rb') as f:
            self.client.post(self.edit_app_url, {'apks': f})

        self.assertEqual(1, App.objects.all().count())
        self.assertEqual(2, Apk.objects.all().count())
        self.assertEqual(2, ApkPointer.objects.all().count())
        self.assertEqual(2, self.app.apkpointer_set.count())

        self.assertTrue(Repository.objects.get(pk=self.repo.pk).update_scheduled)

    def test_reject_non_update(self):
        with open(os.path.join(TEST_FILES_DIR, 'test_1.apk'), 'rb') as f:
            self.client.post(self.edit_app_url, {'apks': f})

        # unset scheduled update, so we can test that no new one was scheduled at the end
        self.repo.update_scheduled = False
        self.repo.save()

        with open(os.path.join(TEST_FILES_DIR, 'test.pdf'), 'rb') as f:
            response = self.client.post(self.edit_app_url, {'apks': f})
            form = response.context['form']
            self.assertTrue(form.has_error('apks'))
            self.assertContains(response,
                                'test.pdf: This file is not an update ' +
                                'for org.bitbucket.tickytacky.mirrormirror')

        self.assertEqual(1, App.objects.all().count())
        self.assertEqual(1, Apk.objects.all().count())
        self.assertEqual(1, ApkPointer.objects.all().count())
        self.assertEqual(1, self.app.apkpointer_set.count())

        self.assertFalse(Repository.objects.get(pk=self.repo.pk).update_scheduled)

    def test_reject_non_update_ajax(self):
        with open(os.path.join(TEST_FILES_DIR, 'test_1.apk'), 'rb') as f:
            self.client.post(self.edit_app_url, {'apks': f})

        # unset scheduled update, so we can test that no new one was scheduled at the end
        self.repo.update_scheduled = False
        self.repo.save()

        with open(os.path.join(TEST_FILES_DIR, 'test.pdf'), 'rb') as f:
            response = self.client.post(self.edit_app_url, {'apks': f},
                                        HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                                        HTTP_RM_BACKGROUND_TYPE='screenshots')
        self.assertContains(response, 'test.pdf: This file is not an update ' +
                            'for org.bitbucket.tickytacky.mirrormirror', status_code=500)

        self.assertEqual(1, App.objects.all().count())
        self.assertEqual(1, Apk.objects.all().count())
        self.assertEqual(1, ApkPointer.objects.all().count())
        self.assertEqual(1, self.app.apkpointer_set.count())

        self.assertFalse(Repository.objects.get(pk=self.repo.pk).update_scheduled)

    def test_upload_screenshot(self):
        self.assertEqual(0, Screenshot.objects.all().count())

        with open(os.path.join(TEST_FILES_DIR, 'test.png'), 'rb') as f:
            self.client.post(self.edit_app_url, {'screenshots': f})

        self.assertEqual(1, Screenshot.objects.all().count())
        self.assertTrue(Repository.objects.get(pk=self.repo.pk).update_scheduled)

    def test_upload_screenshot_ajax(self):
        self.assertEqual(0, Screenshot.objects.all().count())

        with open(os.path.join(TEST_FILES_DIR, 'test.png'), 'rb') as f:
            self.client.post(self.edit_app_url, {'screenshots': f},
                             HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                             HTTP_RM_BACKGROUND_TYPE='screenshots')

        self.assertEqual(1, Screenshot.objects.all().count())
        self.assertTrue(Repository.objects.get(pk=self.repo.pk).update_scheduled)
