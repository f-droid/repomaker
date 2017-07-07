import io
import os
import shutil
from datetime import datetime, timezone
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from maker.models import Repository, RemoteRepository, App, RemoteApp
from .. import TEST_DIR, TEST_MEDIA_DIR, datetime_is_recent


class AppTestCase(TestCase):

    def setUp(self):
        # local objects
        self.user = User.objects.create(username='user2')
        self.repo = Repository.objects.create(user=self.user)
        self.app = App.objects.create(repo=self.repo, package_id='org.example')

        # copy app default icon to test location
        os.makedirs(TEST_MEDIA_DIR)
        shutil.copyfile(os.path.join(settings.MEDIA_ROOT, settings.APP_DEFAULT_ICON),
                        os.path.join(TEST_MEDIA_DIR, settings.APP_DEFAULT_ICON))

        # remote objects
        date = datetime.fromtimestamp(0, timezone.utc)
        self.remote_repo = RemoteRepository.objects.create(last_change_date=date)
        self.remote_app = RemoteApp.objects.create(repo=self.remote_repo, last_updated_date=date)

    def tearDown(self):
        if os.path.isdir(TEST_DIR):
            shutil.rmtree(TEST_DIR)

    @override_settings(MEDIA_ROOT=TEST_MEDIA_DIR)
    def test_from_remote_app(self):
        remote_app = self.remote_app

        # Add content to remote app
        content = {'name': 'app', 'summary': 'foo', 'description': 'bar', 'website': 'site',
                   'author_name': 'author'}
        remote_app.name = content['name']
        remote_app.summary = content['summary']
        remote_app.description = content['description']
        remote_app.website = content['website']
        remote_app.author_name = content['author_name']

        app = App.from_remote_app(repo=self.repo, app=remote_app)
        app.save()

        # assert app was updated properly
        self.assertEqual(content['name'], app.name)
        self.assertEqual(content['summary'], app.summary)
        self.assertEqual(content['description'], app.description)
        self.assertEqual(content['website'], app.website)
        self.assertEqual(content['author_name'], app.author_name)
        self.assertTrue(datetime_is_recent(app.added_date))
        self.assertTrue(datetime_is_recent(app.last_updated_date))

    def test_copy_translations_from_remote_app(self):
        app = self.app
        remote_app = self.remote_app

        # add two translations to RemoteApp
        remote_app.translate(settings.LANGUAGE_CODE)
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
        app = App.objects.language(settings.LANGUAGE_CODE).get(pk=app.pk)
        self.assertEqual('dog', app.l_summary)
        self.assertEqual('cat', app.l_description)

        # assert that German translation was copied
        app = App.objects.language('de').get(pk=app.pk)
        self.assertEqual('hund', app.l_summary)
        self.assertEqual('katze', app.l_description)

    def test_copy_translations_from_remote_app_default_translation(self):
        # copy the non-existent translations to the App
        self.assertEqual(0, len(self.remote_app.get_available_languages()))
        self.app.copy_translations_from_remote_app(self.remote_app)

        # assert that default translation was created
        self.assertEqual([settings.LANGUAGE_CODE], list(self.app.get_available_languages()))

    def test_copy_translations_sanitation(self):
        # add a malicious translation to RemoteApp
        self.remote_app.translate(settings.LANGUAGE_CODE)
        self.remote_app.l_description = '<p>test<script>'
        self.remote_app.save()

        # copy the translations to the App
        self.app.copy_translations_from_remote_app(self.remote_app)

        # assert that malicious content was removed
        self.assertEqual('<p>test</p>', self.app.l_description)

    @override_settings(MEDIA_ROOT=TEST_MEDIA_DIR)
    def test_get_translations_dict(self):
        # load two translations from other test
        self.test_copy_translations_from_remote_app()
        self.assertEqual({settings.LANGUAGE_CODE, 'de'}, set(self.app.get_available_languages()))

        # add also graphic assets
        app = App.objects.language('de').get(pk=self.app.pk)
        app.feature_graphic.save('feature.png', io.BytesIO(b'foo'), save=False)
        app.high_res_icon.save('icon.png', io.BytesIO(b'foo'), save=False)
        app.tv_banner.save('tv.png', io.BytesIO(b'foo'), save=False)
        app.save()

        # get localized dict
        localized = {'en': {'otherKey': 'test'}}
        app._add_translations_to_localized(localized)  # pylint: disable=protected-access

        # assert that dict was created properly
        self.assertEqual({settings.LANGUAGE_CODE, 'de'}, set(localized.keys()))
        self.assertEqual('dog', localized['en']['summary'])
        self.assertEqual('cat', localized['en']['description'])
        self.assertEqual('hund', localized['de']['summary'])
        self.assertEqual('katze', localized['de']['description'])

        # assert that graphic assets are included in dict
        self.assertEqual('feature.png', localized['de']['featureGraphic'])
        self.assertEqual('icon.png', localized['de']['icon'])
        self.assertEqual('tv.png', localized['de']['tvBanner'])

        # assert that existing content is not deleted
        self.assertEqual('test', localized['en']['otherKey'])

    def test_get_translations_dict_not_empty(self):
        # get localized dict
        localized = {}
        self.app._add_translations_to_localized(localized)  # pylint: disable=protected-access

        # default translation should not be included since it is empty
        self.assertFalse(settings.LANGUAGE_CODE in localized)

    @override_settings(MEDIA_ROOT=TEST_MEDIA_DIR)
    @patch('fdroidserver.net.http_get')
    def test_download_graphic_assets_from_remote_app(self, http_get):
        app = self.app
        remote_app = self.remote_app

        # set initial feature graphic for app
        app.translate('de')
        app.save()  # needs to be saved for ForeignKey App to be available when saving file
        app.feature_graphic.save('feature.png', io.BytesIO(b'foo'), save=True)
        old_feature_graphic_path = app.feature_graphic.path
        self.assertTrue(os.path.isfile(old_feature_graphic_path))

        # add graphics to remote app
        remote_app.translate('de')
        remote_app.feature_graphic_url = 'http://url/feature-graphic.png'
        remote_app.feature_graphic_etag = 'etag'
        remote_app.save()

        # download graphic assets
        http_get.return_value = b'icon-data', 'new_etag'
        app.download_graphic_assets_from_remote_app(remote_app)
        http_get.assert_called_once_with(remote_app.feature_graphic_url, 'etag')

        # assert that old feature graphic got deleted and new one was saved
        app = App.objects.language('de').get(pk=app.pk)
        self.assertFalse(os.path.isfile(old_feature_graphic_path))
        self.assertEqual('user_2/repo_1/repo/org.example/de/feature-graphic.png',
                         app.feature_graphic.name)
        self.assertTrue(os.path.isfile(app.feature_graphic.path))

        # assert that new etag was saved
        remote_app = RemoteApp.objects.language('de').get(pk=remote_app.pk)
        self.assertEqual('new_etag', remote_app.feature_graphic_etag)
