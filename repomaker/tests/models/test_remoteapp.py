import io
from datetime import datetime, timezone
from unittest.mock import patch

import os
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from repomaker.models import Repository, RemoteRepository, App, RemoteApp, Apk, ApkPointer, \
    RemoteApkPointer, RemoteScreenshot
from repomaker.models.screenshot import PHONE
from repomaker.storage import get_icon_file_path_for_app
from .. import datetime_is_recent, RmTestCase


# noinspection PyProtectedMember
class RemoteAppTestCase(RmTestCase):
    repo = None
    app = None

    def setUp(self):
        date = datetime.fromtimestamp(1337, timezone.utc)
        self.repo = RemoteRepository.objects.create(name='Test', url='http://repo_url',
                                                    last_change_date=date)
        self.app = RemoteApp.objects.create(repo=self.repo, package_id="org.example",
                                            last_updated_date=date)

    def test_update_from_json_only_when_update(self):
        json = {'name': 'app', 'lastUpdated': 10000}
        self.assertFalse(self.app.update_from_json(json))  # app did not change

    def test_update_from_json(self):
        json = {'name': 'app', 'summary': 'foo', 'description': 'bar<script>', 'webSite': 'site',
                'added': 9999999900000, 'lastUpdated': 9999999900000, 'authorName': 'author'}
        self.assertTrue(self.app.update_from_json(json))  # app changed

        # assert that a default translation was created
        self.assertEqual([settings.LANGUAGE_CODE], list(self.app.get_available_languages()))

        # assert app was updated properly
        self.assertEqual(json['name'], self.app.name)
        self.assertEqual('foo', self.app.summary)
        self.assertEqual('', self.app.summary_override)  # override is not used
        self.assertEqual('bar', self.app.description)  # <script> tag was removed
        self.assertEqual('', self.app.description_override)  # override is not used
        self.assertEqual(json['webSite'], self.app.website)
        self.assertTrue(datetime_is_recent(self.app.added_date))
        last_update = datetime.fromtimestamp(json['lastUpdated'] / 1000, timezone.utc)
        self.assertEqual(last_update, self.app.last_updated_date)
        self.assertEqual(json['authorName'], self.app.author_name)

    def test_update_from_json_moves_overrides(self):
        json = {'name': 'app', 'summary': 'foo', 'description': 'bar<script>',
                'localized': {settings.LANGUAGE_CODE: {'foo': 'bar'}},
                'lastUpdated': 9999999900000}
        self.assertTrue(self.app.update_from_json(json))  # app changed

        # assert app was updated properly
        self.assertEqual('foo', self.app.summary)
        self.assertEqual('', self.app.summary_override)  # override is not used
        self.assertEqual('bar', self.app.description)  # <script> tag was removed
        self.assertEqual('', self.app.description_override)  # override is not used

    def test_update_from_json_moves_override_no_data_loss(self):
        json = {'name': 'app', 'summary': 'foo', 'description': 'bar<script>',
                'localized': {
                    settings.LANGUAGE_CODE: {'summary': 'foo2', 'description': 'bar2<script>'}
                },
                'lastUpdated': 9999999900000}
        self.assertTrue(self.app.update_from_json(json))  # app changed

        # assert app was updated properly
        self.assertEqual('foo2', self.app.summary)
        self.assertEqual('foo', self.app.summary_override)
        self.assertEqual('bar2', self.app.description)  # <script> tag was removed
        self.assertEqual('bar', self.app.description_override)  # <script> tag was removed

    @patch('fdroidserver.net.http_get')
    @patch('repomaker.models.app.App.update_icon')
    def test_update_icon(self, update_icon, http_get):
        # set initial etag and icon for app
        self.app.icon_etag = 'etag'
        self.app.icon.save('test.png', io.BytesIO(b'foo'))
        old_icon_path = self.app.icon.path
        self.assertTrue(os.path.isfile(old_icon_path))

        # create one local app tracking the remote one
        App.objects.create(repo_id=1, package_id=self.app.package_id, tracked_remote=self.app)

        # update icon
        http_get.return_value = b'icon-data', 'new_etag'
        self.app.update_icon('icon.png')  # pylint: disable=protected-access
        http_get.assert_called_once_with(self.repo.url + '/icons-640/icon.png', 'etag')

        # re-retrieve app from database to make sure it was saved
        self.app = RemoteApp.objects.get(pk=self.app.pk)

        # assert that old icon got deleted and new one was saved
        self.assertFalse(os.path.isfile(old_icon_path))
        new_icon_name = get_icon_file_path_for_app(self.app, 'icon.png')
        self.assertEqual(new_icon_name, self.app.icon.name)
        self.assertTrue(os.path.isfile(self.app.icon.path))

        # assert that new etag was saved
        self.assertEqual('new_etag', self.app.icon_etag)

        # assert that local app icons have been updated
        update_icon.called_once_with(self.app.icon)

    def test_update_translations_new(self):
        # update remote app translation with a new one
        localized = {'en': {'summary': 'foo', 'description': 'bar', 'video': 'bla'}}
        self.app._update_translations(localized)  # pylint: disable=protected-access

        # assert that translation has been saved
        app = RemoteApp.objects.language('en').get(pk=self.app.pk)
        self.assertEqual(localized['en']['summary'], app.summary)
        self.assertEqual(localized['en']['description'], app.description)

    def test_update_translations_existing(self):
        # add a new translation
        self.test_update_translations_new()
        self.assertTrue(RemoteApp.objects.language('en').exists())

        # update existing translation
        localized = {'en': {'summary': 'newfoo', 'description': 'newbar', 'video': 'bla'}}
        self.app._update_translations(localized)  # pylint: disable=protected-access

        # assert that translation has been updated
        app = RemoteApp.objects.language('en').get(pk=self.app.pk)
        self.assertEqual(localized['en']['summary'], app.summary)
        self.assertEqual(localized['en']['description'], app.description)

    def test_update_translations_lowercase_language_code(self):
        # update remote app translation with a new one
        localized = {'en-US': {'summary': 'foo', 'description': 'bar', 'featureGraphic': 'test'}}
        self.app._update_translations(localized)  # pylint: disable=protected-access

        # assert that translation has been saved with an all lower-case language code
        app = RemoteApp.objects.language('en-us').get(pk=self.app.pk)
        self.assertEqual(localized['en-US']['summary'], app.summary)
        self.assertEqual(localized['en-US']['description'], app.description)

        # assert that language_code in URL was not changed
        self.assertEqual('http://repo_url/org.example/en-US/test', app.feature_graphic_url)

    def test_apply_translation(self):
        # apply new translation
        translation = {'summary': 'test1', 'description': 'test2', 'featureGraphic': 'feature.png',
                       'icon': 'icon.png', 'tvBanner': 'tv.png'}
        self.app.translate('de')
        self.app.apply_translation('de', translation)

        # assert that translation has been saved
        app = RemoteApp.objects.language('de').get(pk=self.app.pk)
        self.assertEqual(translation['summary'], app.summary)
        self.assertEqual(translation['description'], app.description)
        self.assertEqual('http://repo_url/org.example/de/feature.png', app.feature_graphic_url)
        self.assertEqual('http://repo_url/org.example/de/icon.png', app.high_res_icon_url)
        self.assertEqual('http://repo_url/org.example/de/tv.png', app.tv_banner_url)

    def test_apply_translation_sanitation(self):
        # apply new translation
        translation = {'summary': 'foo', 'description': 'test2<script>'}
        self.app.translate('de')
        self.app.apply_translation('de', translation)

        # assert that translation has no <script> tag
        self.assertEqual(translation['summary'], self.app.summary)
        self.assertEqual('test2', self.app.description)

    def test_update_screenshots(self):
        self.assertEqual(0, RemoteScreenshot.objects.all().count())

        # update remote app screenshots with two new ones
        localized = {'en': {'summary': 'foo', PHONE: ['test1', 'test2']}}
        self.app._update_screenshots(localized)  # pylint: disable=protected-access

        # assert that all screenshots have been saved properly
        screenshots = RemoteScreenshot.objects.all()
        self.assertEqual(2, screenshots.count())
        self.assertEqual(PHONE, screenshots[0].type)
        self.assertEqual(PHONE, screenshots[1].type)
        self.assertEqual('en', screenshots[0].language_code)
        self.assertEqual('en', screenshots[1].language_code)
        self.assertEqual(self.app, screenshots[0].app)
        self.assertEqual(self.app, screenshots[1].app)
        self.assertEqual('http://repo_url/org.example/en/phoneScreenshots/test1',
                         screenshots[0].url)
        self.assertEqual('http://repo_url/org.example/en/phoneScreenshots/test2',
                         screenshots[1].url)

    def test_update_screenshots_lowercase_language_code(self):
        # update remote app screenshots with two new ones
        localized = {'en-US': {'summary': 'foo', PHONE: ['test1', 'test2']}}
        self.app._update_screenshots(localized)  # pylint: disable=protected-access

        # assert that all screenshots have been saved properly
        screenshots = RemoteScreenshot.objects.all()
        self.assertEqual(2, screenshots.count())
        # language code saved in lower-case
        self.assertEqual('en-us', screenshots[0].language_code)
        self.assertEqual('en-us', screenshots[1].language_code)
        # language code in URL left unchanged
        self.assertEqual('http://repo_url/org.example/en-US/phoneScreenshots/test1',
                         screenshots[0].url)
        self.assertEqual('http://repo_url/org.example/en-US/phoneScreenshots/test2',
                         screenshots[1].url)

    @patch('repomaker.tasks.download_remote_screenshot')
    @patch('repomaker.tasks.download_remote_graphic_assets')
    @patch('repomaker.models.apk.Apk.download_async')
    def test_add_to_repo(self, download_async, download_remote_graphic_assets,
                         download_remote_screenshot):
        # create pre-requisites
        self.app.icon.save('test.png', io.BytesIO(b'foo'))
        repo = Repository.objects.create(name='test', user=User.objects.create(username='user2'))
        apk = Apk.objects.create(package_id='org.example')
        remote_apk_pointer = RemoteApkPointer.objects.create(apk=apk, app=self.app, url='test_url')
        remote_screenshot = RemoteScreenshot.objects.create(app=self.app)

        # add remote app to local repo
        app = self.app.add_to_repo(repo)

        # assert that a local App has been created (details should be checked in other tests)
        apps = App.objects.all()
        self.assertEqual(1, apps.count())
        self.assertEqual(app, apps[0])
        self.assertTrue(app.icon.name.endswith('repo/icons-640/test.png'))

        # assert that local ApkPointer got created properly
        apk_pointers = ApkPointer.objects.all()
        self.assertEqual(1, apk_pointers.count())
        apk_pointer = apk_pointers[0]
        self.assertEqual(apk, apk_pointer.apk)

        # assert that all asynchronous tasks have been scheduled
        download_async.assert_called_once_with(remote_apk_pointer.url)
        download_remote_graphic_assets.assert_called_once_with(app.id, self.app.id)
        download_remote_screenshot.assert_called_once_with(remote_screenshot.pk, self.app.pk)

    def test_add_to_repo_without_apks(self):
        # create pre-requisites
        repo = Repository.objects.create(name='test', user=User.objects.create(username='user2'))

        # try to add remote app without any APKs to local repo
        with self.assertRaises(ValidationError):
            self.app.add_to_repo(repo)
