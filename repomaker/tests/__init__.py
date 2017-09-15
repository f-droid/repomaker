import datetime
import os
import shutil
from shutil import copyfile

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from fdroidserver import update
from repomaker import DEFAULT_USER_NAME
from repomaker.models import Repository

TEST_FILES_DIR = os.path.join(settings.BASE_DIR, 'tests')

TEST_DIR = os.path.join(settings.BASE_DIR, 'test_dir')
TEST_MEDIA_DIR = os.path.join(TEST_DIR, 'media')
TEST_PRIVATE_DIR = os.path.join(TEST_DIR, 'private_repo')
TEST_STATIC_DIR = os.path.join(TEST_DIR, 'static')


def datetime_is_recent(dt, seconds=10 * 60):
    now = datetime.datetime.utcnow().timestamp()
    return now - seconds < dt.timestamp() < now


def fake_repo_create(repo):
    if settings.PRIVATE_REPO_ROOT != TEST_PRIVATE_DIR:
        raise RuntimeError('Do not write into non-test directories')

    # copy existing keystore
    src = os.path.join(TEST_FILES_DIR, 'keystore.jks')
    dest = os.path.join(repo.get_private_path(), 'keystore.jks')
    if not os.path.isdir(repo.get_private_path()):
        os.makedirs(repo.get_private_path())
    copyfile(src, dest)
    repo.key_store_pass = 'uGrqvkPLiGptUScrAHsVAyNSQqyJq4OQJSiN1YZWxes='
    repo.key_pass = 'uGrqvkPLiGptUScrAHsVAyNSQqyJq4OQJSiN1YZWxes='

    # make sure that icon directories exist
    for icon_dir in update.get_all_icon_dirs(repo.get_repo_path()):
        if not os.path.exists(icon_dir):
            os.makedirs(icon_dir)


class RmTestCase(TestCase):

    def setUp(self):
        if not settings.SINGLE_USER_MODE:
            user = User.objects.create(username=DEFAULT_USER_NAME)
            self.client.force_login(user=user)
        else:
            user = User.objects.get()

        self.repo = Repository.objects.create(
            name="Test Name",
            description="Test Description",
            url="https://example.org",
            user=user,
        )
        self.repo.chdir()

    def tearDown(self):
        if os.path.isdir(TEST_DIR):
            shutil.rmtree(TEST_DIR)
