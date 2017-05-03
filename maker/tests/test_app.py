import io
import os
import shutil
from datetime import datetime, timezone
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from maker.models import Repository, RemoteRepository, App, RemoteApp
from maker.storage import get_repo_file_path_for_app
from . import TEST_DIR, TEST_MEDIA_DIR, datetime_is_recent


class AppTestCase(TestCase):

    def setUp(self):
        # local objects
        self.user = User.objects.create(username='user2')
        self.repo = Repository.objects.create(user=self.user)
        self.app = App.objects.create(repo=self.repo)

        # remote objects
        date = datetime.fromtimestamp(0, timezone.utc)
        self.remote_repo = RemoteRepository.objects.create(last_change_date=date)
        self.remote_app = RemoteApp.objects.create(repo=self.remote_repo, last_updated_date=date)

    def test_copy_translations_from_remote_app(self):
        app = self.app
        remote_app = self.remote_app

        # add two translations to RemoteApp
        remote_app.translate('en')
        remote_app.l_summary = 'dog'
        remote_app.l_description = 'cat'
        remote_app.save()
        remote_app.translate('de')
        remote_app.l_summary = 'hund'
        remote_app.l_description = 'katze'
        remote_app.save()

        # copy the translations to the App
        app.copy_translations_from_remote_app(remote_app)

        # assert that English translation was copied
        app = RemoteApp.objects.language('en').get(pk=self.app.pk)
        self.assertEqual('dog', app.l_summary)
        self.assertEqual('cat', app.l_description)

        # assert that German translation was copied
        app = RemoteApp.objects.language('de').get(pk=self.app.pk)
        self.assertEqual('hund', app.l_summary)
        self.assertEqual('katze', app.l_description)

    def test_copy_translations_sanitation(self):
        # add a malicious translation to RemoteApp
        self.remote_app.translate('en')
        self.remote_app.l_description = '<p>test<script>'
        self.remote_app.save()

        # copy the translations to the App
        self.app.copy_translations_from_remote_app(self.remote_app)

        # assert that malicious content was removed
        self.assertEqual('<p>test</p>', self.app.l_description)

    def test_get_translations_dict(self):
        # load two translations from other test
        self.test_copy_translations_from_remote_app()
        self.assertEqual({'en', 'de'}, set(self.app.get_available_languages()))

        # get localized dict
        localized = {'en': {'otherKey': 'test'}}
        self.app._add_translations_to_localized(localized)  # pylint: disable=protected-access

        # assert that dict was created properly
        self.assertEqual({'en', 'de'}, set(localized.keys()))
        self.assertEqual('dog', localized['en']['summary'])
        self.assertEqual('cat', localized['en']['description'])
        self.assertEqual('hund', localized['de']['summary'])
        self.assertEqual('katze', localized['de']['description'])

        # assert that existing content is not deleted
        self.assertEqual('test', localized['en']['otherKey'])


@override_settings(MEDIA_ROOT=TEST_MEDIA_DIR)
class RemoteAppTestCase(TestCase):

    def setUp(self):
        date = datetime.fromtimestamp(1337, timezone.utc)
        self.repo = RemoteRepository.objects.create(name='Test', url='http://repo_url',
                                                    last_change_date=date)
        self.app = RemoteApp.objects.create(repo=self.repo, package_id="org.example",
                                            last_updated_date=date)

    def tearDown(self):
        if os.path.isdir(TEST_DIR):
            shutil.rmtree(TEST_DIR)

    def test_update_from_json_only_when_update(self):
        json = {'name': 'app', 'lastUpdated': 10000}
        self.assertFalse(self.app.update_from_json(json))  # app did not change

    def test_update_from_json(self):
        json = {'name': 'app', 'summary': 'foo', 'description': 'bar<script>', 'webSite': 'site',
                'added': 9999999900000, 'lastUpdated': 9999999900000}
        self.assertTrue(self.app.update_from_json(json))  # app changed

        # assert app was updated properly
        self.assertEqual(json['name'], self.app.name)
        self.assertEqual(json['summary'], self.app.summary)
        self.assertEqual('bar', self.app.description)  # <script> tag was removed
        self.assertEqual(json['webSite'], self.app.website)
        self.assertTrue(datetime_is_recent(self.app.added_date))
        last_update = datetime.fromtimestamp(json['lastUpdated'] / 1000, timezone.utc)
        self.assertEqual(last_update, self.app.last_updated_date)

    @patch('fdroidserver.net.http_get')
    def test_update_icon(self, http_get):
        # set initial etag and icon for app
        self.app.icon_etag = 'etag'
        self.app.icon.save('test.png', io.BytesIO(b'foo'))
        old_icon_path = self.app.icon.path
        self.assertTrue(os.path.isfile(old_icon_path))

        # update icon
        http_get.return_value = b'icon-data', 'new_etag'
        self.app._update_icon('icon.png')  # pylint: disable=protected-access
        http_get.assert_called_once_with(self.repo.url + '/icons-640/icon.png', 'etag')

        # assert that old icon got deleted and new one was saved
        self.assertFalse(os.path.isfile(old_icon_path))
        new_icon_name = get_repo_file_path_for_app(self.app, 'icon.png')
        self.assertEqual(new_icon_name, self.app.icon.name)
        self.assertTrue(os.path.isfile(self.app.icon.path))

        # assert that new etag was saved
        self.assertEqual('new_etag', self.app.icon_etag)

    def test_update_translations_new(self):
        # update remote app translation with a new one
        localized = {'en': {'summary': 'foo', 'description': 'bar', 'video': 'bla'}}
        self.app._update_translations(localized)  # pylint: disable=protected-access

        # assert that translation has been saved
        app = RemoteApp.objects.language('en').get(pk=self.app.pk)
        self.assertEqual(localized['en']['summary'], app.l_summary)
        self.assertEqual(localized['en']['description'], app.l_description)

    def test_update_translations_existing(self):
        # add a new translation
        self.test_update_translations_new()
        self.assertTrue(RemoteApp.objects.language('en').exists())

        # update existing translation
        localized = {'en': {'summary': 'newfoo', 'description': 'newbar', 'video': 'bla'}}
        self.app._update_translations(localized)  # pylint: disable=protected-access

        # assert that translation has been updated
        app = RemoteApp.objects.language('en').get(pk=self.app.pk)
        self.assertEqual(localized['en']['summary'], app.l_summary)
        self.assertEqual(localized['en']['description'], app.l_description)

    def test_apply_translation(self):
        # apply new translation
        translation = {'summary': 'test1', 'description': 'test2'}
        self.app.translate('en')
        self.app.apply_translation(translation)

        # assert that translation has been saved
        app = RemoteApp.objects.language('en').get(pk=self.app.pk)
        self.assertEqual(translation['summary'], app.l_summary)
        self.assertEqual(translation['description'], app.l_description)

    def test_apply_translation_sanitation(self):
        # apply new translation
        translation = {'summary': 'foo', 'description': 'test2<script>'}
        self.app.translate('en')
        self.app.apply_translation(translation)

        # assert that translation has no <script> tag
        self.assertEqual(translation['summary'], self.app.l_summary)
        self.assertEqual('test2', self.app.l_description)
