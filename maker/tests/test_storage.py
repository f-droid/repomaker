import os
import shutil
from unittest.mock import patch

from django.test import TestCase, override_settings

from maker.models import Repository, S3Storage, GitStorage, SshStorage
from maker.models.storage import StorageManager
from maker.storage import REPO_DIR, get_repo_path, get_repo_root_path
from . import TEST_DIR


@override_settings(MEDIA_ROOT=TEST_DIR)
class GitStorageTestCase(TestCase):

    def setUp(self):
        self.repo = Repository.objects.create(user_id=1)
        self.storage = GitStorage(repo=self.repo, host="example.org", path="user/repo",
                                  url="https://raw.example.org/user/repo")

    def tearDown(self):
        if os.path.isdir(TEST_DIR):
            shutil.rmtree(TEST_DIR)

    def test_remote_url(self):
        self.assertEqual("git@example.org:user/repo.git", self.storage.get_remote_url())

    @patch('clint.textui.progress.Bar')
    @patch('git.remote.Remote.push')
    def test_publish(self, push, bar):
        # create an empty fake repo
        os.chdir(TEST_DIR)
        os.mkdir(REPO_DIR)

        # publish to git remote storage
        self.storage.publish()

        # assert that git mirror directory exist and that the repo was pushed
        self.assertTrue(os.path.isdir(os.path.join(TEST_DIR, 'git-mirror')))
        self.assertTrue(push.called)
        bar.called = None  # we don't care a about the progress bar, but have to use it


class StorageManagerTestCase(TestCase):

    def setUp(self):
        # create repo and three remote storage locations
        self.repo = Repository.objects.create(user_id=1)
        S3Storage.objects.create(repo=self.repo, bucket='s3_bucket')
        SshStorage.objects.create(repo=self.repo, url='ssh_url')
        GitStorage.objects.create(repo=self.repo, url='git_url')

    def test_storage_models_exist(self):
        # assert that the StorageManager returns at least 3 storage models
        self.assertTrue(len(StorageManager.storage_models) >= 3)

    def test_get_storage(self):
        # assert that all three storage locations are returned by the StorageManager
        self.assertTrue(len(StorageManager.get_storage(self.repo)) == 3)

    def test_add_to_config(self):
        # get config from repo and assert that it doesn't contain storage mirrors
        config = self.repo.get_config()
        self.assertFalse('mirrors' in config)

        # add existing storage mirrors to config
        StorageManager.add_to_config(self.repo, config)

        # assert that we now have all the storage mirrors in the config
        self.assertTrue('mirrors' in config)
        self.assertTrue(len(config['mirrors']) == 3)
        self.assertTrue('https://s3.amazonaws.com/s3_bucket/fdroid/repo' in config['mirrors'])
        self.assertTrue('ssh_url' in config['mirrors'])
        self.assertTrue('git_url/repo' in config['mirrors'])


@override_settings(DEFAULT_REPO_STORAGE=[(os.path.join(TEST_DIR, 'repos'), '/repos/')])
class DefaultStorageTestCase(TestCase):

    def setUp(self):
        self.repo = Repository.objects.create(user_id=1)

    @override_settings(DEFAULT_REPO_STORAGE=None)
    def test_undefined_default_storage(self):
        self.assertTrue(len(StorageManager.get_storage(self.repo)) == 0)

    def test_returned_by_storage_manager(self):
        self.assertTrue(len(StorageManager.get_storage(self.repo)) == 1)

    def test_default_flag(self):
        self.assertTrue(StorageManager.get_storage(self.repo)[0].is_default)

    def test_add_to_config(self):
        # add storage mirrors to config
        config = self.repo.get_config()
        StorageManager.add_to_config(self.repo, config)

        # assert that we now have storage mirror in the config
        self.assertTrue(len(config['mirrors']) == 1)
        url = '/repos/' + get_repo_path(self.repo)
        self.assertEqual(url, config['mirrors'][0])

    @patch('fdroidserver.server.update_serverwebroot')
    def test_publish(self, update_serverwebroot):
        storage = StorageManager.get_storage(self.repo)[0]
        storage.publish()
        local = self.repo.get_repo_path()
        remote = os.path.join(TEST_DIR, 'repos', get_repo_root_path(self.repo))
        update_serverwebroot.assert_called_once_with(remote, local)
