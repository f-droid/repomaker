from unittest.mock import patch

import lxml.html
import django.http
import django.urls
from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse
from repomaker.models import RemoteRepository, RemoteApp, RemoteScreenshot, \
    RemoteApkPointer

from .. import RmTestCase


class RemoteRepositoryViewTest(RmTestCase):

    def setUp(self):
        super().setUp()

        self.remote_repo = RemoteRepository.objects.get(pk=1)

        # Add remote repo to all multi-user mode users
        if not settings.SINGLE_USER_MODE:
            self.remote_repo.users = User.objects.all()

        self.app = RemoteApp.objects.create(repo=self.remote_repo, package_id='org.example',
                                            last_updated_date=self.remote_repo.last_updated_date,
                                            name='App')
        self.app.translate('en')
        self.app.summary = 'Test Summary'
        self.app.description = 'Test Description'
        self.app.save()

        # Add second app only available in German
        self.app2 = RemoteApp.objects.create(repo=self.remote_repo, package_id='org.example2',
                                             last_updated_date=self.remote_repo.last_updated_date,
                                             name='App2')
        self.app2.translate('de')
        self.app2.summary = 'Test Zusammenfassung'
        self.app2.description = 'Test Beschreibung'
        self.app2.save()

        # add a remote screenshot
        self.screenshot = RemoteScreenshot.objects.create(app=self.app, url='test-url',
                                                          language_code=self.app.language_code)

    def test_list_app_translation(self):
        # Request repo app list page and ensure all localized descriptions are shown
        response = self.client.get(reverse('add_app', kwargs={'repo_id': self.repo.id}))
        self.assertContains(response, self.app.summary)
        self.assertContains(response, self.app.description)
        self.assertContains(response, self.app2.description)
        self.assertContains(response, self.app2.description)

    def test_list_app_ajax_translation(self):
        # Request repo app list page via json and ensure all localized descriptions are included
        response = self.client.get(reverse('add_app', kwargs={'repo_id': self.repo.id}),
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(isinstance(response, django.http.JsonResponse))
        json = '[' \
               '{ "categories": [], "description": "Test Description", "repo_id": 1,' \
               '  "lang": "en", "id": 1, "summary": "Test Summary",' \
               '  "icon": "/static/repomaker/images/default-app-icon.png", "added": false,' \
               '  "name": "App"},' \
               '{ "categories": [], "description": "Test Beschreibung", "repo_id": 1,' \
               '  "lang": "de", "id": 2, "summary": "Test Zusammenfassung",' \
               '  "icon": "/static/repomaker/images/default-app-icon.png", "added": false,' \
               '  "name": "App2"}' \
               ']'
        self.assertJSONEqual(response.content.decode(), json)

    def test_list_app_clear_filter_not_visible_when_no_active_filter(self):
        response = self.client.get(reverse('add_app', kwargs={'repo_id': self.repo.id}))
        html = lxml.html.fromstring(response.content)
        elements = html.cssselect('.rm-app-clear-filters')

        self.assertEqual(0, len(elements), 'clear filter link should not be here')

    def test_list_app_clear_filter_visible_when_remote_repo_filter_active(self):
        response = self.client.get(reverse('add_app', kwargs={
            'repo_id': self.repo.id,
            'remote_repo_id': self.remote_repo.id,
        }))

        html = lxml.html.fromstring(response.content)
        elements = html.cssselect('.rm-app-clear-filters a')
        expectedUrl = reverse('add_app', kwargs={'repo_id': self.repo.id})

        self.assertEqual(1, len(elements), 'clear filter link must be here')
        self.assertEqual(expectedUrl, elements[0].attrib['href'])

    def test_list_app_clear_filter_visible_when_category_filter_active(self):
        response = self.client.get(reverse('add_app_with_category', kwargs={
            'repo_id': self.repo.id,
            'category_id': 1,
        }))

        html = lxml.html.fromstring(response.content)
        elements = html.cssselect('.rm-app-clear-filters a')
        expectedUrl = reverse('add_app', kwargs={'repo_id': self.repo.id})

        self.assertEqual(1, len(elements), 'clear filter link must be here')
        self.assertEqual(expectedUrl, elements[0].attrib['href'])

    def test_list_app_clear_filter_visible_when_both_remote_repo_and_category_filters_active(self):
        response = self.client.get(reverse('add_app_with_category', kwargs={
            'repo_id': self.repo.id,
            'remote_repo_id': self.remote_repo.id,
            'category_id': 1,
        }))

        html = lxml.html.fromstring(response.content)
        elements = html.cssselect('.rm-app-clear-filters a')
        expectedUrl = reverse('add_app', kwargs={'repo_id': self.repo.id})

        self.assertEqual(1, len(elements), 'clear filter link must be here')
        self.assertEqual(expectedUrl, elements[0].attrib['href'])

    def test_remote_app_details(self):
        # request remote app detail page
        kwargs = {'repo_id': self.repo.id, 'remote_repo_id': self.remote_repo.id,
                  'app_id': self.app.id, 'lang': self.app.language_code}
        response = self.client.get(reverse('add_remote_app', kwargs=kwargs))

        # assert that localized metadata is shown on the page
        self.assertContains(response, self.app.summary)
        self.assertContains(response, self.app.description)

        # assert that link to show screenshots is shown
        self.assertContains(response, reverse('add_remote_app_screenshots', kwargs=kwargs))

    def test_remote_app_details_screenshot(self):
        # request remote app detail page
        kwargs = {'repo_id': self.repo.id, 'remote_repo_id': self.remote_repo.id,
                  'app_id': self.app.id, 'lang': self.app.language_code}
        response = self.client.get(reverse('add_remote_app_screenshots', kwargs=kwargs))

        # assert that localized metadata is shown on the page
        self.assertContains(response, self.app.summary)
        self.assertContains(response, self.app.description)

        # assert that screenshot is shown
        self.assertContains(response, 'src="'+self.screenshot.url)

    def test_remote_app_details_unknown_lang(self):
        kwargs = {'repo_id': self.repo.id, 'remote_repo_id': self.remote_repo.id,
                  'app_id': self.app.id, 'lang': 'xxx'}
        response = self.client.get(reverse('add_remote_app', kwargs=kwargs))
        self.assertEqual(404, response.status_code)

    def test_remote_app_details_lang_switch(self):
        # translate app to German
        self.app.translate('de')
        self.app.save()

        # request remote app detail page
        kwargs = {'repo_id': self.repo.id, 'remote_repo_id': self.remote_repo.id,
                  'app_id': self.app.id, 'lang': self.app.language_code}
        response = self.client.get(reverse('add_remote_app', kwargs=kwargs))

        # assert that link to both languages is shown on the page
        kwargs['lang'] = 'en'
        self.assertContains(response, 'href="' + reverse('add_remote_app', kwargs=kwargs))
        kwargs['lang'] = 'de'
        self.assertContains(response, 'href="' + reverse('add_remote_app', kwargs=kwargs))

        # request German page and assert that localized metadata is shown on the page
        response = self.client.get(reverse('add_remote_app', kwargs=kwargs))
        self.assertContains(response, self.app.summary)
        self.assertContains(response, self.app.description)

    @patch('repomaker.models.remoteapp.RemoteApp.add_to_repo')
    def test_remote_app_details_add_no_js(self, add_to_repo):
        # one remote APK pointer is required for apps to be added
        RemoteApkPointer.objects.create(app=self.app)

        add_to_repo.return_value.get_absolute_url = lambda: 'test-url'

        # request remote app detail page
        kwargs = {'repo_id': self.repo.id, 'remote_repo_id': self.remote_repo.id,
                  'app_id': self.app.id, 'lang': self.app.language_code}
        response = self.client.post(reverse('add_remote_app', kwargs=kwargs))

        # ensure that app was added and we are redirected to proper page
        add_to_repo.assert_called_once_with(self.repo)
        self.assertTrue(isinstance(response, django.http.HttpResponseRedirect))
        self.assertEqual('test-url', response.url)
