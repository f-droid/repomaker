import io
import json
import os
import shutil
from datetime import datetime, timezone
from unittest.mock import patch

import requests
from background_task.tasks import Task
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files import File
from django.test import TestCase, override_settings
from fdroidserver.update import METADATA_VERSION

from maker.models import App, RemoteApp, Apk, ApkPointer, RemoteApkPointer, Repository, \
    RemoteRepository, S3Storage, SshStorage
from maker.storage import get_repo_file_path, get_remote_repo_path
from . import TEST_FILES_DIR, TEST_DIR, TEST_MEDIA_DIR, TEST_PRIVATE_DIR, datetime_is_recent, \
    fake_repo_create


@override_settings(MEDIA_ROOT=TEST_MEDIA_DIR, PRIVATE_REPO_ROOT=TEST_PRIVATE_DIR)
class RepositoryTestCase(TestCase):

    def setUp(self):
        # create repository
        self.user = User.objects.create(username='user2')
        self.repo = Repository.objects.create(
            name="Test Name",
            description="Test Description",
            url="https://example.org",
            user=self.user,
        )

    def tearDown(self):
        if os.path.isdir(TEST_DIR):
            shutil.rmtree(TEST_DIR)

    def test_repository_creation(self):
        repo = self.repo
        repo.create()

        # assert that metadata was not modified
        self.assertEqual('Test Name', repo.name)
        self.assertEqual('Test Description', repo.description)
        self.assertEqual('https://example.org', repo.url)

        # assert that default icon was used
        self.assertEqual(settings.REPO_DEFAULT_ICON, repo.icon)

        # assert that repo is not scheduled for update or updating already
        self.assertFalse(repo.update_scheduled)
        self.assertFalse(repo.is_updating)

        # assert that the owner of the repository was not modified
        self.assertEqual(self.user.id, repo.user_id)

        # assert all dates were set correctly
        self.assertTrue(datetime_is_recent(repo.last_updated_date))
        self.assertTrue(datetime_is_recent(repo.created_date))
        self.assertIsNone(repo.last_publication_date)

        # assert that the QR code has been created
        qr_rel_path = get_repo_file_path(repo, 'qrcode.png')
        qr_abs_path = os.path.join(settings.MEDIA_ROOT, qr_rel_path)
        self.assertEqual(qr_rel_path, repo.qrcode.name)
        self.assertTrue(os.path.isfile(qr_abs_path))
        self.assertTrue(os.path.getsize(qr_abs_path) > 250)

        # assert that the repo homepage has been created
        page_abs_path = os.path.join(settings.MEDIA_ROOT, get_repo_file_path(repo, 'index.html'))
        self.assertTrue(os.path.isfile(page_abs_path))
        self.assertTrue(os.path.getsize(page_abs_path) > 200)

        # assert that the keys and fingerprint have been created properly
        self.assertTrue(len(repo.public_key) >= 2574)
        self.assertTrue(len(repo.fingerprint) >= 64)
        key_rel_path = os.path.join(repo.get_private_path(), 'keystore.jks')
        key_abs_path = os.path.join(settings.PRIVATE_REPO_ROOT, key_rel_path)
        self.assertTrue(os.path.isfile(key_abs_path))
        self.assertTrue(os.path.getsize(key_abs_path) > 3500)

    def test_get_fingerprint_url(self):
        repo = self.repo
        repo.fingerprint = 'test'
        self.assertEqual(repo.url + '?fingerprint=test', repo.get_fingerprint_url())

    def test_get_fingerprint_url_without_url(self):
        self.repo.url = None
        self.assertIsNone(self.repo.get_fingerprint_url())

    def test_get_mobile_url(self):
        repo = self.repo
        repo.fingerprint = 'test'
        self.assertTrue(repo.get_mobile_url().startswith('fdroidrepo'))

    def test_get_mobile_url_without_url(self):
        self.repo.url = None
        self.assertIsNone(self.repo.get_mobile_url())

    def test_set_url(self):
        repo = self.repo
        old_url = repo.url
        self.assertFalse(repo.qrcode)
        repo.set_url('test/url')
        self.assertNotEqual(old_url, repo.url)
        self.assertTrue(repo.qrcode)

    def test_set_url_to_none(self):
        repo = self.repo
        # assert that a QR code exists before setting the URL
        repo._generate_qrcode()  # pylint: disable=protected-access
        self.assertTrue(repo.qrcode)

        repo.set_url(None)  # unset the URL

        # assert that URL and the QR code got unset
        self.assertIsNone(repo.url)
        self.assertFalse(repo.qrcode)

    def test_empty_repository_update(self):
        repo = self.repo
        fake_repo_create(repo)

        # update the repository
        repo.update()

        # assert that index has been created properly
        index_path = os.path.join(repo.get_repo_path(), 'index-v1.json')
        self.assertTrue(os.path.isfile(index_path))
        with open(index_path, 'r') as f:
            index = json.load(f)

            # assert that there are no packages and no apps
            self.assertEqual({}, index['packages'])
            self.assertEqual([], index['apps'])

            # assert the repository's metadata version matches
            self.assertEqual(METADATA_VERSION, index['repo']['version'])

            # assert repository metadata is as expected
            self.assertEqual(repo.name, index['repo']['name'])
            self.assertEqual(repo.description, index['repo']['description'])

            # TODO do we expect/want a specific timestamp?
            timestamp = datetime.utcfromtimestamp(index['repo']['timestamp'] / 1000)
            self.assertTrue(datetime_is_recent(timestamp))
            self.assertEqual(repo.url, index['repo']['address'])
            self.assertEqual(repo.icon, index['repo']['icon'])

    @patch('maker.models.storage.S3Storage.publish')
    @patch('maker.models.storage.SshStorage.publish')
    def test_publish(self, s3_publish, ssh_publish):
        # create storage objects
        S3Storage.objects.create(repo=self.repo)
        SshStorage.objects.create(repo=self.repo)

        # assert that the repo has never been published
        self.assertIsNone(self.repo.last_publication_date)

        # publish the repository
        self.repo.publish()

        # assert that the repo has a proper publication date now
        self.assertTrue(datetime_is_recent(self.repo.last_publication_date, 5))

        # assert that the storage's publish method's have been called
        s3_publish.assert_called_once_with()
        ssh_publish.assert_called_once_with()

    def test_published_date_not_updated_without_proper_publishing(self):
        # assert that the repo has never been published
        self.assertIsNone(self.repo.last_publication_date)

        # try to publish the repository, which does nothing, because there's no storage
        self.repo.publish()

        # assert that the repo has still not been published
        self.assertIsNone(self.repo.last_publication_date)

    @patch('requests.get')
    def test_full_cyclic_integration(self, get):
        """
        This test creates a local repository with one app
        and then imports it again as a remote repository.
        """
        # create repo
        repo = self.repo
        fake_repo_create(repo)

        # add an app with APK
        apk_hash = '64021f6d632eb5ba55bdeb5c4a78ed612bd3facc25d9a8a5d1c9d5d7a6bcc047'
        app = App.objects.create(repo=repo, package_id='org.bitbucket.tickytacky.mirrormirror',
                                 name='TestApp', summary='TestSummary', description='TestDesc',
                                 website='TestSite', author_name='author')
        apk = Apk.objects.create(package_id='org.bitbucket.tickytacky.mirrormirror', version_code=2,
                                 hash=apk_hash)
        file_path = os.path.join(TEST_FILES_DIR, 'test_1.apk')
        with open(file_path, 'rb') as f:
            apk.file.save('test_1.apk', File(f), save=True)
        apk_pointer = ApkPointer.objects.create(repo=repo, app=app, apk=apk)
        apk_pointer.link_file_from_apk()

        # add localized graphic assets
        app.translate('en')
        app.save()  # needs to be saved for ForeignKey App to be available when saving file
        app.feature_graphic.save('feature.png', io.BytesIO(b'foo'), save=False)
        app.high_res_icon.save('icon.png', io.BytesIO(b'foo'), save=False)
        app.tv_banner.save('tv.png', io.BytesIO(b'foo'), save=False)
        app.save()

        # update repo
        repo.update()

        # prepare the index to be added as a new remote repository
        index_path = os.path.join(repo.get_repo_path(), 'index-v1.jar')
        self.assertTrue(os.path.isfile(index_path))
        with open(index_path, "rb") as file:
            index = file.read()
        get.return_value.content = index

        # add a new remote repository
        date = datetime.fromtimestamp(0, timezone.utc)
        fingerprint = '2E428F3BFCECAE8C0CE9B9E756F6F888044099F3DD0514464DDC90BBF3199EF8'
        remote_repo = RemoteRepository.objects.create(url='test_url', fingerprint=fingerprint,
                                                      last_change_date=date)

        # fetch and update the remote repository
        remote_repo.update_index()
        self.assertTrue(len(remote_repo.public_key) > 500)

        # assert repo and app icon were also downloaded
        self.assertEqual(3, get.call_count)
        get.assert_called_with(  # last get call
            'test_url' + '/icons-640/org.bitbucket.tickytacky.mirrormirror.2.png',
            headers={'User-Agent': 'F-Droid'}
        )

        # assert that a new remote app has been created properly
        remote_apps = RemoteApp.objects.all()
        self.assertEqual(1, len(remote_apps))
        remote_app = remote_apps[0]
        self.assertEqual(app.name, remote_app.name)
        self.assertEqual(app.package_id, remote_app.package_id)
        self.assertEqual(app.summary, remote_app.summary)
        self.assertEqual('<p>'+app.description+'</p>', remote_app.description)
        self.assertEqual(app.website, remote_app.website)
        self.assertEqual(app.author_name, remote_app.author_name)
        self.assertTrue(remote_app.icon)

        # assert that the existing apk got re-used (based on package_id and hash)
        apks = Apk.objects.all()
        self.assertEqual(1, len(apks))
        self.assertEqual(apk, apks[0])

        # assert that there is one RemoteApkPointer now pointing to the same APK
        remote_apk_pointers = RemoteApkPointer.objects.all()
        self.assertEqual(1, len(remote_apk_pointers))
        remote_apk_pointer = remote_apk_pointers[0]
        self.assertEqual(remote_app, remote_apk_pointer.app)
        self.assertEqual(remote_app, remote_apk_pointer.app)
        self.assertEqual(apk, remote_apk_pointer.apk)

        # assert that all graphic assets are pointing to right location
        self.assertTrue('en' in remote_app.get_available_languages())
        remote_app = RemoteApp.objects.language('en').get(pk=remote_app.pk)
        url = 'test_url/org.bitbucket.tickytacky.mirrormirror/en/'
        self.assertEqual(url + 'feature.png', remote_app.feature_graphic_url)
        self.assertEqual(url + 'icon.png', remote_app.high_res_icon_url)
        self.assertEqual(url + 'tv.png', remote_app.tv_banner_url)


@override_settings(MEDIA_ROOT=TEST_MEDIA_DIR)
class RemoteRepositoryTestCase(TestCase):

    def setUp(self):
        self.repo = RemoteRepository.objects.get(pk=1)

    def tearDown(self):
        if os.path.isdir(TEST_DIR):
            shutil.rmtree(TEST_DIR)

    def test_initial_update(self):
        """
        Makes sure that pre-installed remote repositories will be updated on first start.
        """
        tasks = Task.objects.all()
        self.assertTrue(len(tasks) >= 1)
        for task in tasks:
            self.assertEqual('maker.tasks.update_remote_repo', task.task_name)

    @patch('maker.tasks.update_remote_repo')
    def test_update_async(self, update_remote_repo):
        """
        Makes sure that the asynchronous update starts a background task.
        """
        self.repo.update_async()
        update_remote_repo.assert_called_once_with(self.repo.id)
        self.assertTrue(self.repo.update_scheduled)

    @patch('maker.tasks.update_remote_repo')
    def test_update_async_not_called_when_update_scheduled(self, update_remote_repo):
        """
        Makes sure that the asynchronous update does not start another background task
        when another one is scheduled already.
        """
        self.repo.update_scheduled = True
        self.repo.update_async()
        self.assertFalse(update_remote_repo.called)

    @patch('maker.models.repository.RemoteRepository._update_apps')
    @patch('fdroidserver.index.download_repo_index')
    def test_update_index_only_when_new(self, download_repo_index, _update_apps):
        """
        Test that a remote repository is only updated when the index changed since last time.
        """
        download_repo_index.return_value = {
            'repo': {'name': 'Test Name', 'timestamp': 0}
        }, 'etag'
        self.repo.last_change_date = datetime.now(tz=timezone.utc)
        self.repo.update_index(update_apps=True)
        download_repo_index.assert_called_once_with(self.repo.get_fingerprint_url(), etag=None)
        self.assertNotEqual('Test Name', self.repo.name)
        self.assertFalse(_update_apps.called)

    @patch('requests.get')
    @patch('maker.models.repository.RemoteRepository._update_apps')
    @patch('fdroidserver.index.download_repo_index')
    def test_update_index(self, download_repo_index, _update_apps, get):
        """
        Test that a remote repository is updated and a new icon is downloaded.
        """
        # return a fake index
        download_repo_index.return_value = {
            'repo': {
                'name': 'Test Name',
                'description': 'Test <script>Description',
                'icon': 'test-icon.png',
                'timestamp': datetime.utcnow().timestamp() * 1000,
                'mirrors': [
                    'mirror1',
                    'mirror2',
                ],
            },
            'apps': [],
            'packages': [],
        }, 'etag'
        # fake return value of GET request for repository icon
        get.return_value.status_code = requests.codes.ok
        get.return_value.content = b'foo'

        # update index and ensure it would have been downloaded
        repo = self.repo
        repo.update_index(update_apps=True)
        download_repo_index.assert_called_once_with(repo.get_fingerprint_url(), etag=None)

        # assert that the repository metadata was updated with the information from the index
        self.assertEqual('Test Name', repo.name)
        self.assertEqual('Test Description', repo.description)
        self.assertEqual('["mirror1", "mirror2"]', repo.mirrors)

        # assert that new repository icon was downloaded and changed
        get.assert_called_once_with(repo.url + '/' + 'test-icon.png',
                                    headers={'User-Agent': 'F-Droid'})
        self.assertEqual(os.path.join(get_remote_repo_path(repo), 'test-icon.png'), repo.icon.name)

        # assert that an attempt was made to update the apps
        self.assertTrue(_update_apps.called)

    @patch('fdroidserver.net.http_get')
    def test_update_icon_without_pk(self, http_get):
        # create unsaved repo without primary key
        repo = RemoteRepository(url='http://test', last_change_date=datetime.now(tz=timezone.utc))

        # update icon
        http_get.return_value = b'icon-data', 'new_etag'
        repo._update_icon('test.png')  # pylint: disable=protected-access

        # assert that there is no `None` in the path, but the repo number (primary key)
        self.assertFalse('None' in repo.icon.name)
        self.assertTrue(str(repo.pk) in repo.icon.name)
