import io
from datetime import datetime, timezone
from unittest.mock import patch

import os
from background_task.models import Task
from django.conf import settings
from django.core.files.base import ContentFile, File

from repomaker.models import RemoteRepository, App, Apk, RemoteApkPointer, RemoteApp, Screenshot, \
    ApkPointer, Category
from repomaker.models.screenshot import PHONE
from .. import RmTestCase


class AppTestCase(RmTestCase):
    app = None
    remote_repo = None
    remote_app = None

    def setUp(self):
        super().setUp()

        # remote objects
        date = datetime.fromtimestamp(0, timezone.utc)
        self.remote_repo = RemoteRepository.objects.create(last_change_date=date)
        self.remote_app = RemoteApp.objects.create(repo=self.remote_repo, last_updated_date=date)

        # local objects
        self.app = App.objects.create(repo=self.repo, package_id='org.example',
                                      tracked_remote=self.remote_app)

    def test_copy_translations_from_remote_app(self):
        app = self.app
        remote_app = self.remote_app

        # add two translations to RemoteApp
        remote_app.translate('en-us')
        remote_app.summary = 'dog'
        remote_app.description = 'cat'
        remote_app.save()
        remote_app.translate('de')
        remote_app.summary = 'hund'
        remote_app.description = 'katze'
        remote_app.save()

        # copy the translations to the App
        app.copy_translations_from_remote_app(remote_app)

        # assert that English translation was copied
        app = App.objects.language('en-us').get(pk=app.pk)
        self.assertEqual('dog', app.summary)
        self.assertEqual('cat', app.description)

        # assert that German translation was copied
        app = App.objects.language('de').get(pk=app.pk)
        self.assertEqual('hund', app.summary)
        self.assertEqual('katze', app.description)

    def test_copy_translations_from_remote_app_default_translation(self):
        # copy the non-existent translations to the App
        self.assertEqual(0, len(self.remote_app.get_available_languages()))
        self.app.copy_translations_from_remote_app(self.remote_app)

        # assert that default translation was created
        self.assertEqual([settings.LANGUAGE_CODE], list(self.app.get_available_languages()))

    def test_copy_translations_sanitation(self):
        # add a malicious translation to RemoteApp
        self.remote_app.translate(settings.LANGUAGE_CODE)
        self.remote_app.description = '<p>test<script>'
        self.remote_app.save()

        # copy the translations to the App
        self.app.copy_translations_from_remote_app(self.remote_app)

        # assert that malicious content was removed
        self.assertEqual('<p>test</p>', self.app.description)

    def test_get_screenshot_dict(self):
        # create two screenshots
        Screenshot.objects.create(type=PHONE, language_code='en-us', app=self.app,
                                  file=ContentFile(b'foo', name='test1.png'))
        Screenshot.objects.create(type=PHONE, language_code='de', app=self.app,
                                  file=ContentFile(b'foo', name='test2.png'))

        # noinspection PyProtectedMember
        localized = self.app._get_screenshot_dict()  # pylint: disable=protected-access

        # ensure that localized dict gets created properly,
        self.assertEqual(
            {'en-US': {PHONE: ['test1.png']},  # region part of language code should be upper-case
             'de': {PHONE: ['test2.png']}
             }, localized)

    def test_add_translations_to_localized(self):
        # load two translations from other test
        self.test_copy_translations_from_remote_app()
        self.assertEqual({'en-us', 'de'}, set(self.app.get_available_languages()))

        # add also graphic assets
        app = App.objects.language('de').get(pk=self.app.pk)
        app.feature_graphic.save('feature.png', io.BytesIO(b'foo'), save=False)
        app.high_res_icon.save('icon.png', io.BytesIO(b'foo'), save=False)
        app.tv_banner.save('tv.png', io.BytesIO(b'foo'), save=False)
        app.save()

        # get localized dict
        localized = {'en-US': {'otherKey': 'test'}}
        # noinspection PyProtectedMember
        app._add_translations_to_localized(localized)  # pylint: disable=protected-access

        # assert that dict was created properly
        self.assertEqual({'en-US', 'de'}, set(localized.keys()))
        self.assertEqual('dog', localized['en-US']['summary'])
        self.assertEqual('cat', localized['en-US']['description'])
        self.assertEqual('hund', localized['de']['summary'])
        self.assertEqual('katze', localized['de']['description'])

        # assert that graphic assets are included in dict
        self.assertEqual('feature.png', localized['de']['featureGraphic'])
        self.assertEqual('icon.png', localized['de']['icon'])
        self.assertEqual('tv.png', localized['de']['tvBanner'])

        # assert that existing content is not deleted
        self.assertEqual('test', localized['en-US']['otherKey'])

    def test_add_translations_to_localized_not_empty(self):
        # get localized dict
        localized = {}
        # noinspection PyProtectedMember
        self.app._add_translations_to_localized(localized)  # pylint: disable=protected-access

        # default translation should not be included since it is empty
        self.assertFalse(settings.LANGUAGE_CODE in localized)

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
        self.assertEqual('user_1/repo_1/repo/org.example/de/feature-graphic.png',
                         app.feature_graphic.name)
        self.assertTrue(os.path.isfile(app.feature_graphic.path))

        # assert that new etag was saved
        remote_app = RemoteApp.objects.language('de').get(pk=remote_app.pk)
        self.assertEqual('new_etag', remote_app.feature_graphic_etag)

    @patch('repomaker.models.app.App.copy_translations_from_remote_app')
    @patch('repomaker.models.app.App.add_apk_from_tracked_remote_app')
    def test_update_from_tracked_remote_app(self, add_apk_from_tracked_remote_app,
                                            copy_translations_from_remote_app):
        # add information to remote app
        self.remote_app.name = "App Name"
        self.remote_app.author_name = "Author Name"
        self.remote_app.website = "Web Site"
        self.remote_app.category.add(Category.objects.all()[0])
        self.remote_app.category.add(Category.objects.all()[1])

        # add APK and remote pointer to it
        apk = Apk.objects.create(package_id='org.example')
        remote_apk_pointer = RemoteApkPointer.objects.create(apk=apk, app=self.remote_app)

        # call method to be tested
        self.app.update_from_tracked_remote_app(remote_apk_pointer)

        # assert that local app information was updated
        self.assertEqual(self.remote_app.name, self.app.name)
        self.assertEqual(self.remote_app.author_name, self.app.author_name)
        self.assertEqual(self.remote_app.website, self.app.website)
        self.assertSetEqual(self.remote_app.category.all(), self.app.category.all())

        # assert that other methods have been called
        add_apk_from_tracked_remote_app.assert_called_once_with(remote_apk_pointer)
        copy_translations_from_remote_app.assert_called_once_with(self.remote_app)

    def test_add_apk_from_tracked_remote_app_needs_download(self):
        # remove all pre-existing tasks
        Task.objects.all().delete()

        # add APK and remote pointer to it
        apk = Apk.objects.create(package_id='org.example')
        remote_apk_pointer = RemoteApkPointer.objects.create(apk=apk, app=self.remote_app)

        # call method to be tested
        self.app.add_apk_from_tracked_remote_app(remote_apk_pointer)

        # assert that ApkPointer has been created properly
        self.assertEqual(1, ApkPointer.objects.all().count())
        apk_pointer = ApkPointer.objects.get()
        self.assertEqual(apk, apk_pointer.apk)
        self.assertEqual(self.app.repo, apk_pointer.repo)
        self.assertEqual(self.app, apk_pointer.app)
        self.assertFalse(apk_pointer.file)

        # assert that download task was scheduled
        self.assertEqual(1, Task.objects.all().count())
        task = Task.objects.get()
        self.assertEqual('repomaker.tasks.download_apk', task.task_name)
        self.assertJSONEqual(
            '[[' + str(apk_pointer.apk.pk) + ', "' + remote_apk_pointer.url + '"], {}]',
            task.task_params)

    def test_add_apk_from_tracked_remote_app_reuse_file(self):
        # remove all pre-existing tasks
        Task.objects.all().delete()

        # add APK and remote pointer to it
        apk = Apk.objects.create(package_id='org.example')
        file_path = os.path.join(settings.TEST_FILES_DIR, 'test_1.apk')
        with open(file_path, 'rb') as f:
            apk.file.save('test.apk', File(f), save=True)
        remote_apk_pointer = RemoteApkPointer.objects.create(apk=apk, app=self.remote_app)

        # call method to be tested
        self.app.add_apk_from_tracked_remote_app(remote_apk_pointer)

        # assert that ApkPointer has been created properly
        self.assertEqual(1, ApkPointer.objects.all().count())
        apk_pointer = ApkPointer.objects.get()
        self.assertEqual(apk, apk_pointer.apk)
        self.assertEqual(self.app.repo, apk_pointer.repo)
        self.assertEqual(self.app, apk_pointer.app)
        self.assertTrue(apk_pointer.file)
        self.assertTrue(os.path.isfile(apk_pointer.file.path))
        self.assertTrue(apk_pointer.file.name.endswith('test.apk'))

        # assert that no download task was scheduled
        self.assertEqual(0, Task.objects.all().count())

    def test_update_icon(self):
        # create test icons
        old_icon = ContentFile(b'foo', name='test1.png')
        new_icon = ContentFile(b'bar', name='test2.png')

        # add old icon to local app
        self.app.icon = old_icon
        self.app.save()
        old_icon_path = self.app.icon.path
        self.assertTrue(os.path.isfile(old_icon_path))

        # add new icon to remote app
        self.remote_app.icon = new_icon
        self.remote_app.save()
        self.assertTrue(os.path.isfile(self.remote_app.icon.path))

        # update icon from remote app
        self.app.update_icon(new_icon)

        # assert that new icon has been saved properly
        with open(self.app.icon.path, 'r') as f1:
            with open(self.remote_app.icon.path, 'r') as f2:
                self.assertEqual(f1.read(), f2.read())
        self.assertTrue(self.app.icon.name.endswith('test2.png'))

        # assert that old icon was deleted
        self.assertFalse(os.path.isfile(old_icon_path))
