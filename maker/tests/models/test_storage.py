import os
import shutil
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from maker.models import Repository, S3Storage, GitStorage, SshStorage
from maker.models.storage import StorageManager
from maker.storage import REPO_DIR, get_repo_path, get_repo_root_path, PrivateStorage
from .. import TEST_DIR, TEST_MEDIA_DIR, TEST_PRIVATE_DIR


@override_settings(MEDIA_ROOT=TEST_MEDIA_DIR)
class GitStorageTestCase(TestCase):

    def setUp(self):
        self.repo = Repository.objects.create(user=User.objects.create(username='user2'))
        self.storage = GitStorage.objects.create(repo=self.repo,
                                                 host="example.org",
                                                 path="user/repo",
                                                 url="https://raw.example.org/user/repo")

    def tearDown(self):
        if os.path.isdir(TEST_DIR):
            shutil.rmtree(TEST_DIR)

    def test_remote_url(self):
        self.assertEqual("git@example.org:user/repo.git", self.storage.get_remote_url())

    @override_settings(PRIVATE_REPO_ROOT=TEST_PRIVATE_DIR)
    def test_create_identity_file(self):
        storage = self.storage

        # re-declare file storage, so the settings override takes effect
        storage.identity_file.storage = PrivateStorage()

        # assert that there is no public and private key
        self.assertIsNone(storage.public_key)
        self.assertFalse(storage.identity_file)

        # create the key pair
        storage.create_identity_file()

        # assert that there now is a public and private key
        self.assertTrue(len(storage.public_key) > 700)
        self.assertTrue(storage.identity_file)
        path = os.path.join(settings.PRIVATE_REPO_ROOT, storage.identity_file.name)
        self.assertTrue(os.path.isfile(path))

    @override_settings(PRIVATE_REPO_ROOT=TEST_PRIVATE_DIR)
    def test_create_identity_file_does_not_run_twice(self):
        storage = self.storage

        # re-declare file storage, so the settings override takes effect
        storage.identity_file.storage = PrivateStorage()

        # create the key pair
        storage.create_identity_file()

        # assert that there now is a public and private key
        public_key = storage.public_key
        identity_file = storage.identity_file.name

        # create a key pair again
        storage.create_identity_file()

        # assert that nothing has changed
        self.assertEqual(public_key, storage.public_key)
        self.assertEqual(identity_file, storage.identity_file.name)

    @patch('clint.textui.progress.Bar')
    @patch('git.remote.Remote.push')
    def test_publish(self, push, bar):
        # create an empty fake repo
        os.makedirs(TEST_MEDIA_DIR)
        os.chdir(TEST_MEDIA_DIR)
        os.mkdir(REPO_DIR)

        # publish to git remote storage
        self.storage.publish()

        # assert that git mirror directory exist and that the repo was pushed
        self.assertTrue(os.path.isdir(os.path.join(TEST_MEDIA_DIR, 'git-mirror')))
        self.assertTrue(push.called)
        bar.called = None  # we don't care a about the progress bar, but have to use it


class StorageManagerTestCase(TestCase):

    def setUp(self):
        # create repo and three remote storage locations
        self.repo = Repository.objects.create(user=User.objects.create(username='user2'))
        S3Storage.objects.create(repo=self.repo, bucket='s3_bucket')
        SshStorage.objects.create(repo=self.repo, url='ssh_url', disabled=False)
        GitStorage.objects.create(repo=self.repo, url='git_url')

    def test_storage_models_exist(self):
        # assert that the StorageManager returns at least 3 storage models
        self.assertTrue(len(StorageManager.storage_models) >= 3)

    def test_get_storage(self):
        # assert that all three storage locations are returned by the StorageManager
        self.assertTrue(len(StorageManager.get_storage(self.repo)) == 3)

    def test_get_storage_only_enabled(self):
        # assert that only two storage locations are returned by the StorageManager
        self.assertTrue(len(StorageManager.get_storage(self.repo, onlyEnabled=True)) == 2)

    @override_settings(DEFAULT_REPO_STORAGE=[(os.path.join(TEST_MEDIA_DIR, 'repos'), '/repos/')])
    def test_get_default_storage(self):
        self.assertTrue(len(StorageManager.get_default_storage(self.repo)) == 1)

    def test_get_default_storage_without_any_defined(self):
        self.assertTrue(len(StorageManager.get_default_storage(self.repo)) == 0)

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


@override_settings(DEFAULT_REPO_STORAGE=[(os.path.join(TEST_MEDIA_DIR, 'repos'), '/repos/')])
class DefaultStorageTestCase(TestCase):

    def setUp(self):
        self.repo = Repository.objects.create(user=User.objects.create(username='user2'))

    @override_settings(DEFAULT_REPO_STORAGE=None)
    def test_undefined_default_storage(self):
        self.assertTrue(len(StorageManager.get_storage(self.repo)) == 0)

    def test_returned_by_storage_manager(self):
        self.assertTrue(len(StorageManager.get_storage(self.repo)) == 1)

    def test_default_flag(self):
        self.assertTrue(StorageManager.get_storage(self.repo)[0].is_default)

    @override_settings(DEFAULT_REPO_STORAGE=[('repos', 'test/')])
    def test_get_repo_url(self):
        storage = StorageManager.get_storage(self.repo)[0]
        self.assertEqual('test/' + get_repo_path(self.repo), storage.get_repo_url())

    @override_settings(DEFAULT_REPO_STORAGE=[('repos', 'test')])
    def test_get_repo_url_without_trailing_slash(self):
        storage = StorageManager.get_storage(self.repo)[0]
        self.assertEqual('test/' + get_repo_path(self.repo), storage.get_repo_url())

    def test_get_repo_url_without_schema(self):
        storage = StorageManager.get_storage(self.repo)[0]
        self.assertTrue(storage.get_repo_url().startswith('https://example.com' + storage.url))

    def test_add_to_config(self):
        # add storage mirrors to config
        config = self.repo.get_config()
        StorageManager.add_to_config(self.repo, config)

        # assert that we now have storage mirror in the config
        self.assertTrue(len(config['mirrors']) == 1)
        url = 'https://example.com/repos/' + get_repo_path(self.repo)
        self.assertEqual(url, config['mirrors'][0])

    @patch('fdroidserver.server.update_serverwebroot')
    def test_publish(self, update_serverwebroot):
        storage = StorageManager.get_storage(self.repo)[0]
        storage.publish()
        local = self.repo.get_repo_path()
        remote = os.path.join(TEST_MEDIA_DIR, 'repos', get_repo_root_path(self.repo))
        update_serverwebroot.assert_called_once_with(remote, local)
