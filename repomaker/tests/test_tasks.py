from datetime import datetime, timezone
from unittest.mock import patch

import requests
from background_task.tasks import Task
from django.contrib.auth.models import User
from django.test import TestCase
from repomaker import tasks
from repomaker.models import Repository, RemoteRepository, App, RemoteApp, Apk, RemoteScreenshot


class TasksTest(TestCase):

    def setUp(self):
        Task.objects.all().delete()  # delete all initial tasks

    @patch('repomaker.models.repository.Repository.publish')
    @patch('repomaker.models.repository.Repository.update')
    def test_update_repo(self, update, publish):
        # create an actual repository
        repo = Repository.objects.create(user=User.objects.create())

        tasks.update_repo.now(repo.id)  # this repo actually exists

        # assert that repository was updated and published
        update.assert_called_once_with()
        publish.assert_called_once_with()

        # assert that repository is in correct state
        self.assertFalse(repo.update_scheduled)
        self.assertFalse(repo.is_updating)

    @patch('repomaker.models.repository.Repository.publish')
    @patch('repomaker.models.repository.Repository.update')
    def test_update_repo_gone(self, update, publish):
        tasks.update_repo.now(1337)  # this repo ID doesn't exist (anymore?)

        # assert that nothing was updated and published
        self.assertFalse(update.called)
        self.assertFalse(publish.called)

    @patch('repomaker.models.repository.Repository.publish')
    @patch('repomaker.models.repository.Repository.update')
    def test_update_repo_already_running(self, update, publish):
        # create an actual repository
        repo = Repository.objects.create(user=User.objects.create(), is_updating=True)

        tasks.update_repo.now(repo.id)  # this repo actually exists, but is updating already

        # assert that nothing was updated and published
        self.assertFalse(update.called)
        self.assertFalse(publish.called)

    @patch('repomaker.models.remoterepository.RemoteRepository.update_index')
    def test_update_remote_repo(self, update_index):
        # get an actual (pre-installed) remote repository and update its scheduling state
        repo = RemoteRepository.objects.get(pk=1)
        repo.update_scheduled = False
        repo.save()

        tasks.update_remote_repo.now(repo.id)  # this repo actually exists

        # assert that index of remote repository was updated
        update_index.assert_called_once_with()

        # assert that repository is in correct state
        self.assertFalse(repo.update_scheduled)
        self.assertFalse(repo.is_updating)

    @patch('repomaker.models.remoterepository.RemoteRepository.update_index')
    def test_update_remote_repo_gone(self, update_index):
        tasks.update_remote_repo.now(1337)  # this repo ID doesn't exist (anymore?)

        # assert that nothing was updated and published
        self.assertFalse(update_index.called)

    @patch('repomaker.models.remoterepository.RemoteRepository.update_index')
    def test_update_remote_repo_already_running(self, update_index):
        # get an actual (pre-installed) remote repository and set it to updating
        repo = RemoteRepository.objects.get(pk=1)
        repo.is_updating = True
        repo.save()

        tasks.update_remote_repo.now(repo.id)  # this repo actually exists, but is updating already

        # assert that nothing was updated and published
        self.assertFalse(update_index.called)

    @patch('repomaker.models.remoteapp.RemoteApp.update_icon')
    def test_update_remote_app_icon(self, update_icon):
        remote_app = RemoteApp.objects.create(
            repo=RemoteRepository.objects.get(pk=1),
            last_updated_date=datetime.fromtimestamp(0, timezone.utc)
        )

        tasks.update_remote_app_icon.now(remote_app.id, "icon name")

        # assert that index of remote repository was updated
        update_icon.assert_called_once_with("icon name")

    @patch('repomaker.models.remoteapp.RemoteApp.update_icon')
    def test_update_remote_app_icon_gone(self, update_icon):
        tasks.update_remote_app_icon.now(1337, "icon name")  # this app ID doesn't exist (anymore?)

        # assert that nothing was updated and published
        self.assertFalse(update_icon.called)

    @patch('repomaker.models.apk.Apk.download')
    def test_download_apk(self, download):
        # create an APK
        apk = Apk.objects.create()

        tasks.download_apk.now(apk.id, 'test_url')  # this APK actually exists

        # assert that APK was downloaded
        download.assert_called_once_with('test_url')

        # assert that APK is in correct state
        self.assertFalse(apk.is_downloading)

    @patch('repomaker.models.apk.Apk.download')
    def test_download_apk_gone(self, download):
        tasks.download_apk.now(1337, None)  # this APK ID doesn't exist (anymore?)

        # assert that nothing was downloaded
        self.assertFalse(download.called)

    @patch('repomaker.models.apk.Apk.download')
    def test_download_apk_already_running(self, download):
        # create an APK and set it to downloading
        apk = Apk.objects.create(is_downloading=True)

        tasks.download_apk.now(apk.id, None)  # this APK actually exists, but is downloading already

        # assert that nothing was downloaded
        self.assertFalse(download.called)

    @patch('repomaker.models.app.App.download_graphic_assets_from_remote_app')
    def test_download_remote_graphic_assets(self, download_graphic_assets_from_remote_app):
        repo = Repository.objects.create(user=User.objects.create())
        app = App.objects.create(repo=repo)
        date = datetime.fromtimestamp(0, timezone.utc)
        remote_repo = RemoteRepository.objects.create(last_change_date=date)
        remote_app = RemoteApp.objects.create(repo=remote_repo, last_updated_date=date)

        tasks.download_remote_graphic_assets.now(app.id, remote_app.id)

        # assert that APK was downloaded
        download_graphic_assets_from_remote_app.assert_called_once_with(remote_app)

    @patch('repomaker.models.app.App.download_graphic_assets_from_remote_app')
    def test_download_remote_graphic_assets_no_app(self, download_graphic_assets_from_remote_app):
        date = datetime.fromtimestamp(0, timezone.utc)
        remote_repo = RemoteRepository.objects.create(last_change_date=date)
        remote_app = RemoteApp.objects.create(repo=remote_repo, last_updated_date=date)

        tasks.download_remote_graphic_assets.now(1337, remote_app.id)

        # assert that downloaded was not scheduled
        self.assertFalse(download_graphic_assets_from_remote_app.called)

    @patch('repomaker.models.app.App.download_graphic_assets_from_remote_app')
    def test_download_remote_graphic_assets_no_remote_app(self,
                                                          download_graphic_assets_from_remote_app):
        repo = Repository.objects.create(user=User.objects.create())
        app = App.objects.create(repo=repo)

        tasks.download_remote_graphic_assets.now(app.id, 1337)

        # assert that downloaded was not scheduled
        self.assertFalse(download_graphic_assets_from_remote_app.called)

    @patch('repomaker.models.screenshot.RemoteScreenshot.download')
    def test_download_remote_screenshot(self, download):
        date = datetime.fromtimestamp(0, timezone.utc)
        remote_repo = RemoteRepository.objects.create(last_change_date=date)
        remote_app = RemoteApp.objects.create(repo=remote_repo, last_updated_date=date)
        screenshot = RemoteScreenshot.objects.create(app=remote_app)

        tasks.download_remote_screenshot.now(screenshot.id, remote_app.id)

        # assert that screenshot was downloaded
        download.assert_called_once_with(remote_app.id)

    @patch('repomaker.models.screenshot.RemoteScreenshot.download')
    def test_download_remote_screenshot_gone(self, download):
        tasks.download_remote_screenshot.now(1337, 1337)

        # assert that screenshot was not downloaded
        self.assertFalse(download.called)

    @patch('requests.get')
    def test_download_remote_screenshot_app_gone(self, get):
        date = datetime.fromtimestamp(0, timezone.utc)
        remote_repo = RemoteRepository.objects.create(last_change_date=date)
        remote_app = RemoteApp.objects.create(repo=remote_repo, last_updated_date=date)
        screenshot = RemoteScreenshot.objects.create(app=remote_app, url='test')

        # fake return values of GET request
        get.return_value.status_code = requests.codes.ok
        get.return_value.content = b'foo'

        tasks.download_remote_screenshot.now(screenshot.id, 1337)

        # assert that screenshot was downloaded
        get.assert_called_once_with(screenshot.url)

    def test_priorities(self):
        # create an actual repository and an APK
        repo = Repository.objects.create(user=User.objects.create())
        apk = Apk.objects.create()

        # schedule repo update first and then APK download
        repo.update_async()
        apk.download_async('url')
        # TODO add other types of background tasks here

        # assert that APK download task comes first with a higher priority
        available_tasks = Task.objects.find_available()
        self.assertEqual(2, available_tasks.count())
        self.assertEqual('repomaker.tasks.download_apk', available_tasks[0].task_name)
        self.assertEqual('repomaker.tasks.update_repo', available_tasks[1].task_name)
        self.assertTrue(available_tasks[0].priority > available_tasks[1].priority)
