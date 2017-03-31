import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage


REPO_DIR = 'repo'


def get_media_file_path(repo, filename):
    if hasattr(repo, 'user'):
        return 'user_{0}/{1}'.format(repo.user.pk, filename)
    else:
        return 'remote_repo_{0}/{1}'.format(repo.pk, filename)


def get_media_file_path_for_app(app, filename):
    return 'user_{0}/{1}'.format(app.repo.user.pk, filename)


def get_private_user_path(repo):
    return 'user_{0}'.format(repo.user.pk)


def get_repo_path(repo):
    return os.path.join(get_private_user_path(repo), 'repo_{0}'.format(repo.pk))


def get_remote_repo_path(repo):
    return os.path.join('remote', 'repo_{0}'.format(repo.pk))


def get_apk_file_path(apk, filename):
    return os.path.join(get_repo_path(apk.app.repo), REPO_DIR, filename)


def get_identity_file_path(storage, filename):
    return os.path.join(get_repo_path(storage.repo), filename)


class RepoStorage(FileSystemStorage):
    def __init__(self, file_permissions_mode=None, directory_permissions_mode=None):
        super().__init__(settings.REPO_ROOT, None, file_permissions_mode,
                         directory_permissions_mode)
