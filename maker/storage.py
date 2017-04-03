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
    if hasattr(app.repo, 'user'):
        return 'user_{0}/{1}'.format(app.repo.user.pk, filename)
    else:
        return 'remote_repo_{0}/{1}'.format(app.repo.pk, filename)


def get_private_user_path(repo):
    return 'user_{0}'.format(repo.user.pk)


def get_repo_path(repo):
    return os.path.join(get_private_user_path(repo), 'repo_{0}'.format(repo.pk))


def get_remote_repo_path(repo):
    return os.path.join('remote', 'repo_{0}'.format(repo.pk))


def get_apk_file_path(apk, filename):
    if hasattr(apk, 'repo'):
        return os.path.join(get_repo_path(apk.repo), REPO_DIR, filename)
    else:
        return os.path.join('packages', filename)


def get_identity_file_path(storage, filename):
    return os.path.join(get_repo_path(storage.repo), filename)


class RepoStorage(FileSystemStorage):
    def __init__(self, file_permissions_mode=None, directory_permissions_mode=None):
        super(RepoStorage, self).__init__(settings.REPO_ROOT, None, file_permissions_mode,
                                          directory_permissions_mode)

    def link(self, source, target):
        """
        Links or copies the source file to the target file.
        :param source: path to source file relative to self.location
        :param target: path to target file relative to self.location
        :return: The final relative path to the target file, can be different from :param target
        """
        target_dir = os.path.dirname(target)
        abs_source = os.path.join(self.location, source)
        abs_target = os.path.join(self.location, target)
        abs_target = self.get_available_name(abs_target)
        target_path = os.path.dirname(abs_target)

        if not os.path.exists(target_path):
            os.makedirs(target_path)
        # TODO support operating systems without support for os.link()
        os.link(abs_source, abs_target)

        rel_target = os.path.join(target_dir, os.path.basename(abs_target))
        return rel_target
