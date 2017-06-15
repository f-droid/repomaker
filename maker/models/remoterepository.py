import datetime
import json
import logging
import os
from io import BytesIO

from allauth.account.signals import user_signed_up
from background_task.tasks import Task
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.dispatch import receiver
from django.utils import timezone
from fdroidserver import index, net

from maker import tasks
from maker.models.repository import AbstractRepository
from maker.storage import get_remote_repo_path
from maker.utils import clean


class RemoteRepository(AbstractRepository):
    users = models.ManyToManyField(User)
    pre_installed = models.BooleanField(default=False)
    index_etag = models.CharField(max_length=128, blank=True, null=True)
    icon_etag = models.CharField(max_length=128, blank=True, null=True)
    mirrors = models.TextField(blank=True)
    disabled = models.BooleanField(default=False)
    last_change_date = models.DateTimeField()

    def get_path(self):
        return os.path.join(settings.MEDIA_ROOT, get_remote_repo_path(self))

    def update_async(self):
        """
        Schedules the repository to be updated asynchronously from remote location
        """
        if self.update_scheduled:
            return  # no need to update a repo twice with same data
        self.update_scheduled = True
        self.save()
        # pylint: disable=unexpected-keyword-arg
        tasks.update_remote_repo(self.id, repeat=Task.DAILY, priority=-2)

    def update_index(self, update_apps=True):
        """
        Downloads the remote index and passes it to update()

        :raises: VerificationException() if the index can not be validated anymore
        """
        self.get_config()
        repo_index, etag = index.download_repo_index(self.get_fingerprint_url(),
                                                     etag=self.index_etag)
        if repo_index is None:
            logging.info("Remote repo ETag for '%s' did not change, not updating.", str(self))
            return  # the index did not change since last time

        try:
            self._update(repo_index, update_apps)  # also saves at the end
        except Exception as e:
            # reset date of last change, so the update will be re-tried
            self.last_change_date = datetime.datetime.fromtimestamp(0, timezone.utc)
            raise e

        if update_apps:  # TODO improve this once the workflow has been designed
            self.index_etag = etag  # don't set etag when only adding the repo, so it fetches again
            self.save()

    def _update(self, repo_index, update_apps):
        """
        Updates this remote repository with the given index

        :param repo_index: The repository index v1 in JSON format
        :param update_apps: False if apps should not be updated as well
        """
        # bail out if the repo did not change since last update
        repo_change = datetime.datetime.fromtimestamp(repo_index['repo']['timestamp'] / 1000,
                                                      timezone.utc)
        if self.last_change_date and self.last_change_date >= repo_change:
            logging.info("Remote repo date for %s did not change, not updating.", str(self))
            return

        # update repository's metadata
        self.name = repo_index['repo']['name']
        self.description = clean(repo_index['repo']['description'])
        if 'mirrors' in repo_index['repo']:
            self.mirrors = json.dumps(repo_index['repo']['mirrors'])
        if update_apps:
            self.last_change_date = repo_change
        else:
            # apps will be updated asynchronously soon, so this allows the update to pass
            self.last_change_date = datetime.datetime.fromtimestamp(0, timezone.utc)
        if not self.public_key:
            self.public_key = repo_index['repo']['pubkey']  # added by index.download_repo_index()

        # download and save repository icon
        try:
            self._update_icon(repo_index['repo']['icon'])
        except Exception as e:
            logging.warning("Could not download repository icon. %s", e)

        self.save()

        if update_apps:
            self._update_apps(repo_index['apps'], repo_index['packages'])

    def _update_icon(self, icon_name):
        url = self.url + '/icons/' + icon_name
        icon, etag = net.http_get(url, self.icon_etag)
        if icon is None:
            return  # icon did not change
        if not self.pk:
            self.save()  # to ensure the primary key exists, to be used for the file path
        self.delete_old_icon()
        self.icon_etag = etag
        self.icon.save(icon_name, BytesIO(icon), save=False)

    def _update_apps(self, apps, packages):
        from maker.models.remoteapp import RemoteApp
        # update the apps from this repo and remember all package names we have seen
        package_names = []
        for app in apps:
            if app['packageName'] not in packages:
                logging.info("App %s has no packages, so ignore it.", app['packageName'])
                continue

            # query for existing remote apps, if this repo was already saved
            if self.pk:
                query_set = RemoteApp.objects.filter(repo=self, package_id=app['packageName'])

            # update existing app or create a new one
            if self.pk and query_set.exists():
                app_obj = query_set.get()
            else:
                app_obj = RemoteApp(package_id=app['packageName'], repo=self)
            package_names.append(app['packageName'])
            changed = app_obj.update_from_json(app)  # this also saves the app_obj

            if changed:
                # update packages belonging to app
                for package in packages[app['packageName']]:
                    self._update_package(app_obj, package)

        # remove apps that no longer exist
        self._remove_old_apps(package_names)

    def _update_package(self, app, package_info):
        from maker.models import Apk, RemoteApkPointer

        apks = Apk.objects.filter(package_id=package_info['packageName'], hash=package_info['hash'])
        if apks.exists():
            apk = apks.get()
        else:
            apk = Apk()
            apk.apply_json_package_info(package_info)
            apk.save()

        pointers = RemoteApkPointer.objects.filter(apk=apk, app=app)
        if not pointers.exists():
            pointer = RemoteApkPointer(
                apk=apk,
                app=app,
                url=self.url + "/" + package_info['apkName'],
            )
            pointer.save()

    def _remove_old_apps(self, packages):
        """
        Removes old apps from the database and this repository.

        :param packages: A list of package names that should not be removed
        """
        from maker.models.remoteapp import RemoteApp
        old_apps = RemoteApp.objects.filter(repo=self)
        for app in old_apps.all():
            if app.package_id not in packages:
                app.delete()

    class Meta(AbstractRepository.Meta):
        verbose_name_plural = "Remote Repositories"


@receiver(user_signed_up)
def after_user_signed_up(**kwargs):
    # add new user to all pre-installed repositories
    user = kwargs['user']
    for remote_repo in RemoteRepository.objects.filter(pre_installed=True).all():
        remote_repo.users.add(user)
