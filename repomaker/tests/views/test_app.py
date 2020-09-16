import io

import os
from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse

from repomaker import DEFAULT_USER_NAME
from repomaker.models import App, Apk, ApkPointer, Repository, Screenshot, RemoteRepository, \
    RemoteApp
from .. import RmTestCase


class AppViewTestCase(RmTestCase):
    app = None

    def setUp(self):
        super().setUp()

        # create app in repo
        self.app = App.objects.create(repo=self.repo,
                                      package_id='org.bitbucket.tickytacky.mirrormirror',
                                      name='TestApp', website='TestSite', author_name='author')
        # translate app in default language
        self.app.translate(settings.LANGUAGE_CODE)
        self.app.summary = 'Test Summary'
        self.app.description = 'Test Description'
        self.app.save()

    def test_app_detail_default_lang_redirect(self):
        kwargs = {'repo_id': self.app.repo.pk, 'app_id': self.app.pk}
        response = self.client.get(reverse('app', kwargs=kwargs))
        self.assertRedirects(response, self.app.get_absolute_url())

    def test_app_detail_default_lang(self):
        # save screenshot and feature graphic
        screenshot = Screenshot.objects.create(app=self.app, language_code=self.app.language_code)
        screenshot.file.save('screenshot.png', io.BytesIO(b'foo'), save=True)
        self.app.feature_graphic.save('feature.png', io.BytesIO(b'foo'), save=True)

        response = self.client.get(self.app.get_absolute_url())
        self.assertEqual(200, response.status_code)
        self.assertContains(response, self.app.name)
        self.assertContains(response, self.app.author_name)
        self.assertContains(response, self.app.summary)
        self.assertContains(response, self.app.description)
        self.assertContains(response, 'src="' + screenshot.file.url)
        self.assertContains(response, 'src="' + self.app.feature_graphic.url)

    def test_app_detail_other_lang(self):
        self.translate_to_de()
        self.assertTrue('/de/' in self.app.get_absolute_url())

        response = self.client.get(self.app.get_absolute_url())
        self.assertContains(response, 'Test-Zusammenfassung')
        self.assertContains(response, 'Test-Beschreibung')

        # ensure that there is a link to the default language
        app = App.objects.language(settings.LANGUAGE_CODE).get(pk=self.app.pk)
        self.assertFalse('/de/' in app.get_absolute_url())
        self.assertTrue('/' + settings.LANGUAGE_CODE + '/' in app.get_absolute_url())
        self.assertContains(response, app.get_absolute_url())

    def test_app_detail_prev_next(self):
        # create a second app in a different language
        app2 = App.objects.create(repo=self.repo, package_id='org.example', name='Example')
        app2.translate('de')
        app2.save()

        # ensure first app has a link to the next one
        response = self.client.get(self.app.get_absolute_url())
        self.assertEqual(self.app, response.context['app'])
        with self.assertRaises(App.DoesNotExist):
            self.app.get_previous()
        self.assertContains(response, self.app.get_next().get_absolute_url())

        # ensure second app has a link back to the previous one
        response = self.client.get(self.app.get_next().get_absolute_url())
        self.assertEqual(app2, response.context['app'])
        self.assertContains(response, app2.get_previous().get_absolute_url())
        with self.assertRaises(App.DoesNotExist):
            app2.get_next()

    def test_app_edit_default_lang(self):
        response = self.client.get(self.app.get_edit_url())
        self.assertEqual(200, response.status_code)
        self.assertContains(response, self.app.name)
        self.assertContains(response, self.app.author_name)
        self.assertContains(response, self.app.summary)
        self.assertContains(response, self.app.description)

    def test_app_edit_other_lang(self):
        self.translate_to_de()
        self.assertTrue('/de/' in self.app.get_edit_url())

        response = self.client.get(self.app.get_edit_url())
        self.assertContains(response, 'Test-Zusammenfassung')
        self.assertContains(response, 'Test-Beschreibung')

        # ensure that there is a link to the default language
        app = App.objects.language(settings.LANGUAGE_CODE).get(pk=self.app.pk)
        self.assertFalse('/de/' in app.get_absolute_url())
        self.assertTrue('/' + settings.LANGUAGE_CODE + '/' in app.get_edit_url())
        self.assertContains(response, app.get_edit_url())

    def test_app_edit_unknown_lang(self):
        kwargs = {'repo_id': self.repo.pk, 'app_id': self.app.pk, 'lang': 'xxx'}
        response = self.client.get(reverse('app_edit', kwargs=kwargs))
        self.assertEqual(404, response.status_code)

    def test_app_edit_prev_next(self):
        # create a second app in a different language
        app2 = App.objects.create(repo=self.repo, package_id='org.example', name='Example')
        app2.translate('de')
        app2.save()

        # ensure first app has a link to the next one
        response = self.client.get(self.app.get_edit_url())
        self.assertEqual(self.app, response.context['app'])
        with self.assertRaises(App.DoesNotExist):
            self.app.get_previous()
        self.assertContains(response, self.app.get_next().get_edit_url())

        # ensure second app has a link back to the previous one
        response = self.client.get(self.app.get_next().get_edit_url())
        self.assertEqual(app2, response.context['app'])
        self.assertContains(response, app2.get_previous().get_edit_url())
        with self.assertRaises(App.DoesNotExist):
            app2.get_next()

    def test_app_edit_remove_tracking(self):
        # make the local app track a remote one
        remote_repo = RemoteRepository.objects.get(pk=1)
        remote_app = RemoteApp.objects.create(repo=remote_repo,
                                              package_id='org.bitbucket.tickytacky.mirrormirror',
                                              last_updated_date=remote_repo.last_updated_date)
        self.app.tracked_remote = remote_app
        self.app.save()

        # try editing the app and find out that is is disabled due to app tracking
        response = self.client.get(self.app.get_edit_url())
        self.assertContains(response, 'Editing Disabled')
        self.assertContains(response, 'disable-app-tracking')
        self.assertNotContains(response, response.context['form']['summary'])

        # remove the app tracking, so editing will be enabled
        response = self.client.post(self.app.get_edit_url(), {'disable-app-tracking': 'true'})
        self.assertRedirects(response, self.app.get_edit_url())

        # update app from database and ensure it is no longer tracking the remote app
        self.app = App.objects.get(pk=self.app.pk)
        self.assertIsNone(self.app.tracked_remote)

        # try editing the app again and ensure that it is now working
        response = self.client.get(self.app.get_edit_url())
        self.assertNotContains(response, 'Editing Disabled')
        self.assertNotContains(response, 'disable-app-tracking')
        self.assertContains(response, response.context['form']['summary'])

    def test_upload_apk_and_update(self):
        self.assertEqual(1, App.objects.all().count())
        self.assertEqual(0, Apk.objects.all().count())
        self.assertEqual(0, ApkPointer.objects.all().count())

        with open(os.path.join(settings.TEST_FILES_DIR, 'test_1.apk'), 'rb') as f:
            self.client.post(self.app.get_edit_url(), {'apks': f})

        self.assertEqual(1, App.objects.all().count())
        self.assertEqual(1, Apk.objects.all().count())
        self.assertEqual(1, ApkPointer.objects.all().count())
        self.assertEqual(1, self.app.apkpointer_set.count())

        with open(os.path.join(settings.TEST_FILES_DIR, 'test_2.apk'), 'rb') as f:
            self.client.post(self.app.get_edit_url(), {'apks': f})

        self.assertEqual(1, App.objects.all().count())
        self.assertEqual(2, Apk.objects.all().count())
        self.assertEqual(2, ApkPointer.objects.all().count())
        self.assertEqual(2, self.app.apkpointer_set.count())

        self.assertTrue(Repository.objects.get(pk=self.repo.pk).update_scheduled)

    def test_reject_non_update(self):
        with open(os.path.join(settings.TEST_FILES_DIR, 'test_1.apk'), 'rb') as f:
            self.client.post(self.app.get_edit_url(), {'apks': f})

        # unset scheduled update, so we can test that no new one was scheduled at the end
        self.repo.update_scheduled = False
        self.repo.save()

        with open(os.path.join(settings.TEST_FILES_DIR, 'test.pdf'), 'rb') as f:
            response = self.client.post(self.app.get_edit_url(), {'apks': f})
            form = response.context['form']
            self.assertTrue(form.has_error('apks'))
            self.assertContains(response,
                                'This file is not an update ' +
                                'for org.bitbucket.tickytacky.mirrormirror')

        self.assertEqual(1, App.objects.all().count())
        self.assertEqual(1, Apk.objects.all().count())
        self.assertEqual(1, ApkPointer.objects.all().count())
        self.assertEqual(1, self.app.apkpointer_set.count())

        self.assertFalse(Repository.objects.get(pk=self.repo.pk).update_scheduled)

    def test_reject_non_update_ajax(self):
        with open(os.path.join(settings.TEST_FILES_DIR, 'test_1.apk'), 'rb') as f:
            self.client.post(self.app.get_edit_url(), {'apks': f})

        # unset scheduled update, so we can test that no new one was scheduled at the end
        self.repo.update_scheduled = False
        self.repo.save()

        with open(os.path.join(settings.TEST_FILES_DIR, 'test.pdf'), 'rb') as f:
            response = self.client.post(self.app.get_edit_url(), {'apks': f},
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

        with open(os.path.join(settings.TEST_FILES_DIR, 'test.png'), 'rb') as f:
            self.client.post(self.app.get_edit_url(), {'screenshots': f})

        self.assertEqual(1, Screenshot.objects.all().count())
        self.assertTrue(Repository.objects.get(pk=self.repo.pk).update_scheduled)

    def test_upload_screenshot_ajax(self):
        self.assertEqual(0, Screenshot.objects.all().count())

        with open(os.path.join(settings.TEST_FILES_DIR, 'test.png'), 'rb') as f:
            response = self.client.post(self.app.get_edit_url(), {'screenshots': f},
                                        HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                                        HTTP_RM_BACKGROUND_TYPE='screenshots')

        self.assertEqual(1, Screenshot.objects.all().count())
        self.assertTrue(Repository.objects.get(pk=self.repo.pk).update_scheduled)

        self.assertContains(response, self.repo.id)
        self.assertContains(response, self.app.id)
        self.assertContains(response, 'screenshots')

        screenshot = Screenshot.objects.get(app=self.app.id)
        self.assertContains(response, screenshot.id)
        self.assertContains(response, screenshot.file.url)

    def test_upload_feature_graphic(self):
        # manually add a feature graphic and ensure that its file exists
        self.app.feature_graphic.save('old.png', io.BytesIO(b'foo'), save=True)
        old_graphic = self.app.feature_graphic.path
        self.assertTrue(os.path.isfile(old_graphic))

        with open(os.path.join(settings.TEST_FILES_DIR, 'test.png'), 'rb') as f:
            self.client.post(self.app.get_edit_url(), {'feature_graphic': f})

        # refresh app object and assert that graphic got saved and old one removed
        self.app = App.objects.get(pk=self.app.pk)
        self.assertTrue(self.app.feature_graphic)
        self.assertTrue(self.app.feature_graphic.name.endswith('/test.png'))
        self.assertFalse(os.path.isfile(old_graphic))
        self.assertTrue(Repository.objects.get(pk=self.repo.pk).update_scheduled)

    def test_upload_feature_graphic_ajax(self):
        # manually add a feature graphic and ensure that its file exists
        self.app.feature_graphic.save('old.png', io.BytesIO(b'foo'), save=True)
        old_graphic = self.app.feature_graphic.path
        self.assertTrue(os.path.isfile(old_graphic))

        with open(os.path.join(settings.TEST_FILES_DIR, 'test.png'), 'rb') as f:
            response = self.client.post(self.app.get_edit_url(), {'feature-graphic': f},
                                        HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                                        HTTP_RM_BACKGROUND_TYPE='feature-graphic')

        # refresh app object and assert that graphic got saved and old one removed
        self.app = App.objects.get(pk=self.app.pk)
        self.assertTrue(self.app.feature_graphic)
        self.assertTrue(self.app.feature_graphic.name.endswith('/test.png'))
        self.assertFalse(os.path.isfile(old_graphic))
        self.assertTrue(Repository.objects.get(pk=self.repo.pk).update_scheduled)

        self.assertContains(response, self.app.repo.id)
        self.assertContains(response, self.app.id)
        self.assertContains(response, 'feature-graphic')
        self.assertContains(response, self.app.feature_graphic.url)

    def test_upload_apk(self):
        self.assertEqual(0, Apk.objects.all().count())

        with open(os.path.join(settings.TEST_FILES_DIR, 'test_1.apk'), 'rb') as f:
            self.client.post(self.app.get_edit_url(), {'apks': f})

        self.assertEqual(1, Apk.objects.all().count())
        self.assertTrue(Repository.objects.get(pk=self.repo.pk).update_scheduled)

    def test_upload_apk_ajax(self):
        self.assertEqual(0, Apk.objects.all().count())

        with open(os.path.join(settings.TEST_FILES_DIR, 'test_1.apk'), 'rb') as f:
            response = self.client.post(self.app.get_edit_url(), {'apks': f},
                                        HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(1, Apk.objects.all().count())
        self.assertTrue(Repository.objects.get(pk=self.repo.pk).update_scheduled)

        self.assertContains(response, self.repo.id)
        self.assertContains(response, self.app.id)
        self.assertContains(response, 'apks')

        apk_pointer = ApkPointer.objects.get(app=self.app.id)
        self.assertContains(response, apk_pointer.id)
        self.assertContains(response, apk_pointer.apk.version_name)
        self.assertContains(response, apk_pointer.apk.version_code)

        # Create another repo and app and add the same APK there to test again with two pointers
        repo2 = Repository.objects.create(
            name="Test Name 2",
            description="Test Description",
            url="https://example.org",
            user=User.objects.get(username=DEFAULT_USER_NAME),
        )
        # create app in repo
        app2 = App.objects.create(repo=repo2,
                                  package_id='org.bitbucket.tickytacky.mirrormirror',
                                  name='TestApp', website='TestSite', author_name='author')
        app2.translate(settings.LANGUAGE_CODE)
        app2.save()

        with open(os.path.join(settings.TEST_FILES_DIR, 'test_1.apk'), 'rb') as f:
            response = self.client.post(app2.get_edit_url(), {'apks': f},
                                        HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(1, Apk.objects.all().count())
        self.assertEqual(2, ApkPointer.objects.all().count())
        self.assertTrue(Repository.objects.get(pk=repo2.pk).update_scheduled)

        self.assertContains(response, repo2.id)
        self.assertContains(response, app2.id)
        self.assertContains(response, 'apks')

        apk_pointer = ApkPointer.objects.get(app=app2.id)
        self.assertContains(response, apk_pointer.id)
        self.assertContains(response, apk_pointer.apk.version_name)
        self.assertContains(response, apk_pointer.apk.version_code)

    def test_add_lang(self):
        self.assertFalse('de' in self.app.get_available_languages())
        kwargs = {'repo_id': self.repo.pk, 'app_id': self.app.pk}
        data = {
            'lang': 'de',
            'summary': 'Test-Zusammenfassung',
            'description': 'Test-Beschreibung',
        }
        response = self.client.post(reverse('app_add_lang', kwargs=kwargs), data)
        kwargs['lang'] = 'de'
        self.assertRedirects(response, reverse('app', kwargs=kwargs))
        self.assertTrue('de' in self.app.get_available_languages())

        # assert data was saved properly
        self.app = App.objects.language('de').get(pk=self.app.pk)
        self.assertEqual(data['summary'], self.app.summary)
        self.assertEqual(data['description'], self.app.description)
        self.assertTrue(Repository.objects.get(pk=self.repo.pk).update_scheduled)

    def test_add_lang_exists(self):
        self.translate_to_de()
        kwargs = {'repo_id': self.repo.pk, 'app_id': self.app.pk}
        response = self.client.post(reverse('app_add_lang', kwargs=kwargs), {'lang': 'de'})
        self.assertEqual(200, response.status_code)
        self.assertEqual('This language already exists. Please choose another one!',
                         response.context['form'].errors['lang'])
        self.assertContains(response, response.context['form'].errors['lang'])

    def test_add_lang_invalid(self):
        kwargs = {'repo_id': self.repo.pk, 'app_id': self.app.pk}
        response = self.client.post(reverse('app_add_lang', kwargs=kwargs), {'lang': '123'})
        self.assertEqual(200, response.status_code)
        self.assertEqual('This is not a valid language code.',
                         response.context['form'].errors['lang'])
        self.assertContains(response, response.context['form'].errors['lang'])

    def test_add_lang_converted_to_lower_case(self):
        kwargs = {'repo_id': self.repo.pk, 'app_id': self.app.pk}
        response = self.client.post(reverse('app_add_lang', kwargs=kwargs), {'lang': 'de-DE'})
        kwargs['lang'] = 'de-de'
        self.assertRedirects(response, reverse('app', kwargs=kwargs))
        self.assertEqual({settings.LANGUAGE_CODE, 'de-de'}, set(self.app.get_available_languages()))

    def test_delete_feature_graphic(self):
        self.app.feature_graphic.save('feature.png', io.BytesIO(b'foo'), save=True)
        feature_graphic = self.app.feature_graphic.path
        self.assertTrue(os.path.isfile(feature_graphic))

        kwargs = {'repo_id': self.repo.pk, 'app_id': self.app.pk}
        response = self.client.get(reverse('delete_feature_graphic', kwargs=kwargs))

        # assert that it contains the relevant information
        self.assertContains(response, self.app.name)
        self.assertContains(response, 'src="' + self.app.feature_graphic.url)

        # request the feature graphic to be deleted
        response = self.client.post(reverse('delete_feature_graphic', kwargs=kwargs))

        self.assertRedirects(response, self.app.get_edit_url())
        self.assertFalse(os.path.isfile(feature_graphic))

    def translate_to_de(self):
        self.app.translate('de')
        self.app.summary = 'Test-Zusammenfassung'
        self.app.description = 'Test-Beschreibung'
        self.app.save()
