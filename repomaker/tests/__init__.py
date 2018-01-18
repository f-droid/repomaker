import datetime
import shutil
from shutil import copyfile

import os
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from fdroidserver import update

from repomaker import DEFAULT_USER_NAME
from repomaker.models import Repository


def datetime_is_recent(dt, seconds=10 * 60):
    now = datetime.datetime.utcnow().timestamp()
    return now - seconds < dt.timestamp() < now


def fake_repo_create(repo):
    # copy existing keystore
    src = os.path.join(settings.TEST_FILES_DIR, 'keystore.jks')
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
    user = None
    repo = None

    def setUp(self):
        if not settings.SINGLE_USER_MODE:
            self.user = User.objects.create(username=DEFAULT_USER_NAME)
            self.client.force_login(user=self.user)
        else:
            self.user = User.objects.get()

        self.repo = Repository.objects.create(
            name="Test Name",
            description="Test Description",
            url="https://example.org",
            fingerprint="foongerprint",
            user=self.user,
        )
        self.repo.chdir()

    def tearDown(self):
        if os.path.isdir(settings.TEST_DIR):
            shutil.rmtree(settings.TEST_DIR)
