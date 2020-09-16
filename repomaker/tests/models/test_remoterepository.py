from datetime import datetime, timezone
from unittest.mock import Mock, patch

import background_task
import os
import requests
from background_task.tasks import Task
from django.conf import settings
from django.contrib.auth.models import User
from requests.exceptions import HTTPError

from repomaker.models import App, Apk, ApkPointer, RemoteApkPointer, RemoteApp, Repository, \
    RemoteRepository
from repomaker.models.repository import AbstractRepository
from repomaker.storage import get_remote_repo_path
from repomaker.tasks import PRIORITY_REMOTE_REPO
from .. import RmTestCase


# noinspection PyProtectedMember
class RemoteRepositoryTestCase(RmTestCase):
    remote_repo = None

    def setUp(self):
        super().setUp()
        self.remote_repo = RemoteRepository.objects.get(pk=1)

    def test_get_path(self):
        self.assertEqual(os.path.join(settings.MEDIA_ROOT, 'remote_repo_1'),
                         self.remote_repo.get_path())
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
        self.remote_repo.update_scheduled = False

        self.remote_repo.update_async()
        update_remote_repo.assert_called_once_with(self.remote_repo.id, repeat=Task.DAILY,
                                                   priority=PRIORITY_REMOTE_REPO)
        self.assertTrue(self.remote_repo.update_scheduled)

    @patch('repomaker.tasks.update_remote_repo')
    def test_update_async_not_called_when_update_scheduled(self, update_remote_repo):
        """
        Makes sure that the asynchronous update does not start another background task
        when another one is scheduled already.
        """
        self.remote_repo.update_scheduled = True
        self.remote_repo.update_async()
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
        self.remote_repo.last_change_date = datetime.now(tz=timezone.utc)
        self.remote_repo.update_index(update_apps=True)
        download_repo_index.assert_called_once_with(self.remote_repo.get_fingerprint_url(),
                                                    etag=None)
        self.assertNotEqual('Test Name', self.remote_repo.name)
        self.assertFalse(_update_apps.called)

    @patch('repomaker.models.remoterepository.RemoteRepository._update_apps')
    @patch('fdroidserver.index.download_repo_index')
    def test_update_index_only_when_not_none(self, download_repo_index, _update_apps):
        """
        Test that a remote repository is only updated when the index changed since last time.
        """
        download_repo_index.return_value = None, 'etag'
        self.remote_repo.update_index(update_apps=True)
        download_repo_index.assert_called_once_with(self.remote_repo.get_fingerprint_url(),
                                                    etag=None)
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
        repo = self.remote_repo
        repo.update_index(update_apps=True)
        download_repo_index.assert_called_once_with(repo.get_fingerprint_url(), etag=None)

        # assert that the repository metadata was updated with the information from the index
        self.assertEqual('Test Name', repo.name)
        self.assertEqual('Test Description', repo.description)
        self.assertEqual('["mirror1", "mirror2"]', repo.mirrors)

        # assert that new repository icon was downloaded and changed
        get.assert_called_once_with(repo.url + '/icons/' + 'test-icon.png',
                                    headers={'User-Agent': 'F-Droid'},
                                    timeout=600)
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
            self.remote_repo.update_index(update_apps=True)
        download_repo_index.assert_called_once_with(self.remote_repo.get_fingerprint_url(),
                                                    etag=None)

        update_from_json.assert_called_once_with(index['apps'][0])
        self.assertEqual(datetime.fromtimestamp(0, timezone.utc), self.remote_repo.last_change_date)
        self.assertIsNone(self.remote_repo.index_etag)

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
        self.assertFalse(self.remote_repo.disabled)

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
        self.remote_repo = RemoteRepository.objects.get(pk=1)
        self.assertTrue(self.remote_repo.disabled)

    def test_update_apps(self):
        # update apps from fake index, should insert one remote app
        self.assertEqual(0, RemoteApp.objects.all().count())
        apps = [
            {'packageName': 'org.example',
             'name': 'Test App',
             'summary': 'Summary',
             'description': 'Test Description',
             'lastUpdated': datetime.utcnow().timestamp() * 1000,
             }
        ]
        packages = {
            'org.example': [{
                'packageName': 'org.example',
                'apkName': 'org.example.1.apk',
                'hash': 'testhash1',
                'hashType': 'sha256',
                'versionCode': 1,
                'versionName': '0.1',
                'size': 42,
            }]
        }
        self.remote_repo._update_apps(apps, packages)  # pylint: disable=protected-access

        # assert that remote app was imported correctly
        self.assertEqual(1, RemoteApp.objects.all().count())
        remote_app = RemoteApp.objects.get()
        self.assertEqual(1, len(remote_app.get_available_languages()))
        self.assertEqual(apps[0]['packageName'], remote_app.package_id)
        self.assertEqual(apps[0]['name'], remote_app.name)
        self.assertEqual('Test Description', remote_app.description)

        # create an App that is tracking the RemoteApp
        app = remote_app.add_to_repo(self.repo)
        self.assertEqual(remote_app, app.tracked_remote)
        self.assertEqual(1, ApkPointer.objects.all().count())

        # add a new package to the index
        packages['org.example'].append({
            'packageName': 'org.example',
            'apkName': 'org.example.42.apk',
            'hash': 'testhash2',
            'hashType': 'sha256',
            'versionCode': 42,
            'versionName': '1.0',
            'size': 1337,
        })

        # remove old tasks before next update
        Task.objects.all().delete()

        # update apps again with the new package (and updated app)
        del apps[0]['localized']
        apps[0]['name'] += ' New'
        apps[0]['summary'] = 'New Summary'
        apps[0]['description'] = 'New Description'
        apps[0]['authorName'] = 'Author'
        apps[0]['webSite'] = 'https://example.org'
        apps[0]['lastUpdated'] += 1
        self.remote_repo._update_apps(apps, packages)  # pylint: disable=protected-access

        # assert that the package was properly imported as an Apk
        self.assertEqual(2, Apk.objects.all().count())
        apk = Apk.objects.get(pk=2)
        self.assertEqual('org.example', apk.package_id)
        self.assertEqual('testhash2', apk.hash)
        self.assertEqual('sha256', apk.hash_type)

        # assert that a RemoteApkPointer is pointing properly to that Apk
        self.assertEqual(2, RemoteApkPointer.objects.all().count())
        remote_apk_pointer = RemoteApkPointer.objects.get(pk=2)
        self.assertEqual(apk, remote_apk_pointer.apk)
        self.assertEqual(remote_app, remote_apk_pointer.app)
        self.assertEqual(self.remote_repo.url + '/org.example.42.apk', remote_apk_pointer.url)

        # assert that a ApkPointer is pointing properly to that Apk
        self.assertEqual(2, ApkPointer.objects.all().count())
        apk_pointer = ApkPointer.objects.get(pk=2)
        self.assertEqual(apk, apk_pointer.apk)
        self.assertEqual(app, apk_pointer.app)
        self.assertEqual(app.repo, apk_pointer.repo)

        # assert that the Apk is scheduled to be downloaded, so it can be added to the App
        self.assertEqual(1, Task.objects.all().count())
        task = Task.objects.get()
        self.assertEqual('repomaker.tasks.download_apk', task.task_name)
        self.assertJSONEqual(
            '[[' + str(apk_pointer.apk.pk) + ', "' + remote_apk_pointer.url + '"], {}]',
            task.task_params)

        # assert that the app metadata was updated as well
        app = App.objects.get(pk=app.pk)
        self.assertEqual(apps[0]['name'], app.name)
        self.assertEqual('New Summary', app.summary)
        self.assertEqual('New Description', app.description)
        self.assertEqual(apps[0]['authorName'], app.author_name)
        self.assertEqual(apps[0]['webSite'], app.website)

    def test_remove_old_apps(self):
        RemoteApp.objects.create(repo=self.remote_repo, package_id="delete",
                                 last_updated_date=self.remote_repo.last_updated_date)
        RemoteApp.objects.create(repo=self.remote_repo, package_id="do not delete",
                                 last_updated_date=self.remote_repo.last_updated_date)
        packages = ["do not delete"]
        self.remote_repo._remove_old_apps(packages)  # pylint: disable=protected-access

        # assert that only the expected app was deleted
        self.assertEqual(1, RemoteApp.objects.count())
        self.assertEqual("do not delete", RemoteApp.objects.all()[0].package_id)

    def test_remove_old_apps_thousands(self):
        """
        Tests that we do not run into sqlite3.OperationalError: too many SQL variables
        """
        RemoteApp.objects.create(repo=self.remote_repo, package_id="delete",
                                 last_updated_date=self.remote_repo.last_updated_date)
        # add lots of fake packages
        packages = []
        for i in range(1, 3000):
            packages.append(str(i))
        self.remote_repo._remove_old_apps(packages)  # pylint: disable=protected-access

        # assert that all remote apps could be deleted
        self.assertFalse(RemoteApp.objects.exists())

    def test_is_in_repo(self):
        repo = Repository.objects.create(user=User.objects.create_user('user2'))
        app = App.objects.create(repo=repo, package_id="org.example")
        remote_app = RemoteApp.objects.create(repo=self.remote_repo, package_id="org.example",
                                              last_updated_date=self.remote_repo.last_updated_date)
        self.assertTrue(remote_app.is_in_repo(repo))

        app.package_id = "different"
        app.save()
        self.assertFalse(remote_app.is_in_repo(repo))
