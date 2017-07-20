import os
import shutil
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import background_task
import requests
from background_task.tasks import Task
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from requests.exceptions import HTTPError

from repomaker.models import App, RemoteApp, Repository, \
    RemoteRepository
from repomaker.models.repository import AbstractRepository
from repomaker.storage import get_remote_repo_path
from .. import TEST_DIR, TEST_MEDIA_DIR


@override_settings(MEDIA_ROOT=TEST_MEDIA_DIR)
class RemoteRepositoryTestCase(TestCase):

    def setUp(self):
        self.repo = RemoteRepository.objects.get(pk=1)

    def tearDown(self):
        if os.path.isdir(TEST_DIR):
            shutil.rmtree(TEST_DIR)

    def test_get_path(self):
        self.assertEqual(os.path.join(settings.MEDIA_ROOT, 'remote_repo_1'), self.repo.get_path())
        with self.assertRaises(NotImplementedError):
            AbstractRepository().get_repo_path()

    def test_initial_update(self):
        """
        Makes sure that pre-installed remote repositories will be updated on first start.
        """
        tasks = Task.objects.all()
        self.assertTrue(len(tasks) >= 1)
        for task in tasks:
            self.assertEqual('repomaker.tasks.update_remote_repo', task.task_name)

    @patch('repomaker.tasks.update_remote_repo')
    def test_update_async(self, update_remote_repo):
        """
        Makes sure that the asynchronous update starts a background task.
        """
        self.repo.update_scheduled = False

        self.repo.update_async()
        update_remote_repo.assert_called_once_with(self.repo.id, repeat=Task.DAILY, priority=-2)
        self.assertTrue(self.repo.update_scheduled)

    @patch('repomaker.tasks.update_remote_repo')
    def test_update_async_not_called_when_update_scheduled(self, update_remote_repo):
        """
        Makes sure that the asynchronous update does not start another background task
        when another one is scheduled already.
        """
        self.repo.update_scheduled = True
        self.repo.update_async()
        self.assertFalse(update_remote_repo.called)

    @patch('repomaker.models.remoterepository.RemoteRepository._update_apps')
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

    @patch('repomaker.models.remoterepository.RemoteRepository._update_apps')
    @patch('fdroidserver.index.download_repo_index')
    def test_update_index_only_when_not_none(self, download_repo_index, _update_apps):
        """
        Test that a remote repository is only updated when the index changed since last time.
        """
        download_repo_index.return_value = None, 'etag'
        self.repo.update_index(update_apps=True)
        download_repo_index.assert_called_once_with(self.repo.get_fingerprint_url(), etag=None)
        self.assertFalse(_update_apps.called)

    @patch('requests.get')
    @patch('repomaker.models.remoterepository.RemoteRepository._update_apps')
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
        get.assert_called_once_with(repo.url + '/icons/' + 'test-icon.png',
                                    headers={'User-Agent': 'F-Droid'})
        self.assertEqual(os.path.join(get_remote_repo_path(repo), 'test-icon.png'), repo.icon.name)

        # assert that an attempt was made to update the apps
        self.assertTrue(_update_apps.called)

    @patch('repomaker.models.remoteapp.RemoteApp.update_from_json')
    @patch('fdroidserver.index.download_repo_index')
    def test_update_index_retry_when_failed(self, download_repo_index, update_from_json):
        """
        Test that a remote repository is only updated when the index changed since last time.
        """
        # return a fake index
        index = {
            'repo': {
               'name': 'Test Name',
               'description': 'Test Description',
               'timestamp': datetime.utcnow().timestamp() * 1000,
            },
            'apps': [
               {
                   'packageName': 'org.example',
                   'name': 'test app',
                   'lastUpdated': datetime.utcnow().timestamp() * 1000,
               },
            ],
            'packages': {
               'org.example': []
            },
        }
        download_repo_index.return_value = index, 'etag'
        update_from_json.side_effect = HTTPError(Mock(status=502))

        with self.assertRaises(HTTPError):
            self.repo.update_index(update_apps=True)
        download_repo_index.assert_called_once_with(self.repo.get_fingerprint_url(), etag=None)

        update_from_json.assert_called_once_with(index['apps'][0])
        self.assertEqual(datetime.fromtimestamp(0, timezone.utc), self.repo.last_change_date)
        self.assertIsNone(self.repo.index_etag)

    @patch('fdroidserver.net.http_get')
    def test_update_icon_without_pk(self, http_get):
        # create unsaved repo without primary key
        repo = RemoteRepository(url='http://test', last_change_date=datetime.now(tz=timezone.utc))

        # update icon
        http_get.return_value = b'icon-data', 'new_etag'
        repo._update_icon('test.png')  # pylint: disable=protected-access

        http_get.assert_called_once_with('http://test/icons/test.png', None)

        # assert that there is no `None` in the path, but the repo number (primary key)
        self.assertFalse('None' in repo.icon.name)
        self.assertTrue(str(repo.pk) in repo.icon.name)

    @patch('fdroidserver.index.download_repo_index')
    def test_fail(self, download_repo_index):
        # assert that pre-installed remote repository is initially enabled
        self.assertFalse(self.repo.disabled)

        # get initial update task from pre-installed remote repository
        all_tasks = Task.objects.all()
        self.assertEqual(2, all_tasks.count())
        task = all_tasks[0]

        # set initial update task to be one short of the maximum number of attempts
        task.attempts = settings.MAX_ATTEMPTS - 1
        task.save()

        # run the task and provide it with malformed data, so it fails
        download_repo_index.return_value = 'malformed', None
        background_task.tasks.tasks.run_next_task()
        self.assertEqual(1, download_repo_index.call_count)

        # ensure that remote repository got disabled
        self.repo = RemoteRepository.objects.get(pk=1)
        self.assertTrue(self.repo.disabled)

    def test_remove_old_apps(self):
        RemoteApp.objects.create(repo=self.repo, package_id="delete",
                                 last_updated_date=self.repo.last_updated_date)
        RemoteApp.objects.create(repo=self.repo, package_id="do not delete",
                                 last_updated_date=self.repo.last_updated_date)
        packages = ["do not delete"]
        self.repo._remove_old_apps(packages)  # pylint: disable=protected-access

        # assert that only the expected app was deleted
        self.assertEqual(1, RemoteApp.objects.count())
        self.assertEqual("do not delete", RemoteApp.objects.all()[0].package_id)

    def test_remove_old_apps_thousands(self):
        """
        Tests that we do not run into sqlite3.OperationalError: too many SQL variables
        """
        RemoteApp.objects.create(repo=self.repo, package_id="delete",
                                 last_updated_date=self.repo.last_updated_date)
        # add lots of fake packages
        packages = []
        for i in range(1, 3000):
            packages.append(str(i))
        self.repo._remove_old_apps(packages)  # pylint: disable=protected-access

        # assert that all remote apps could be deleted
        self.assertFalse(RemoteApp.objects.exists())

    def test_is_in_repo(self):
        repo = Repository.objects.create(user=User.objects.create_user('user2'))
        app = App.objects.create(repo=repo, package_id="org.example")
        remote_app = RemoteApp.objects.create(repo=self.repo, package_id="org.example",
                                              last_updated_date=self.repo.last_updated_date)
        self.assertTrue(remote_app.is_in_repo(repo))

        app.package_id = "different"
        app.save()
        self.assertFalse(remote_app.is_in_repo(repo))
