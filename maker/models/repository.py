import datetime
import json
import logging
import os
from io import BytesIO
from shutil import copy

import qrcode
from allauth.account.signals import user_signed_up
from background_task.tasks import Task
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.db import models
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from fdroidserver import common, index, server, update, net

from maker import tasks
from maker.storage import REPO_DIR, get_repo_file_path, get_remote_repo_path, get_repo_root_path
from maker.utils import clean


class AbstractRepository(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    url = models.URLField(max_length=2048, blank=True, null=True)
    icon = models.ImageField(upload_to=get_repo_file_path, default=settings.REPO_DEFAULT_ICON)
    public_key = models.TextField(blank=True)
    fingerprint = models.CharField(max_length=512, blank=True)
    update_scheduled = models.BooleanField(default=False)
    is_updating = models.BooleanField(default=False)
    last_updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name

    def get_path(self):
        raise NotImplementedError()

    def get_repo_path(self):
        return os.path.join(self.get_path(), REPO_DIR)

    def get_fingerprint_url(self):
        if not self.url:
            return None
        return self.url + "?fingerprint=" + self.fingerprint

    def get_mobile_url(self):
        if not self.get_fingerprint_url():
            return None
        return self.get_fingerprint_url().replace('http', 'fdroidrepo', 1)

    def delete_old_icon(self):
        icon_path = os.path.dirname(self.icon.path)
        if icon_path != settings.MEDIA_ROOT:
            self.icon.delete(save=False)

    def get_config(self):
        config = {}
        common.fill_config_defaults(config)
        common.config = config
        common.options = Options
        update.config = config
        update.options = Options
        server.config = config
        server.options = Options
        return config


class Repository(AbstractRepository):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    qrcode = models.ImageField(upload_to=get_repo_file_path, blank=True)
    key_store_pass = models.CharField(max_length=64)
    key_pass = models.CharField(max_length=64)
    created_date = models.DateTimeField(default=timezone.now)
    last_publication_date = models.DateTimeField(null=True, blank=True)

    def get_absolute_url(self):
        return reverse('repo', kwargs={'repo_id': self.pk})

    def get_private_path(self):
        return os.path.join(settings.PRIVATE_REPO_ROOT, get_repo_root_path(self))

    def get_path(self):
        return os.path.join(settings.MEDIA_ROOT, get_repo_root_path(self))

    def get_config(self):
        config = super().get_config()
        config.update({
            'repo_url': self.url,
            'repo_name': self.name,
            'repo_icon': os.path.join(settings.MEDIA_ROOT, self.icon.name),
            'repo_description': self.description,
            'repo_keyalias': 'Key Alias',
            'keydname': 'CN=repomaker.f-droid.org, OU=F-Droid',
            'keystore': os.path.join(self.get_private_path(), 'keystore.jks'),
            'keystorepass': self.key_store_pass,
            'keypass': self.key_pass,
            'nonstandardwebroot': True,  # TODO remove this when storage URLs are standardized
        })
        if self.public_key is not None:
            config['repo_pubkey'] = self.public_key
        return config

    def chdir(self):
        """
        Change into path for user's local repository
        """
        repo_local_path = self.get_path()
        if not os.path.exists(repo_local_path):
            os.makedirs(repo_local_path)
        os.chdir(repo_local_path)

    def create(self):
        """
        Creates the repository on disk including the keystore.
        This also sets the public key and fingerprint for :param repo.
        """
        self.key_store_pass = common.genpassword()
        self.key_pass = common.genpassword()

        self.chdir()
        config = self.get_config()

        # Ensure icon directories exist
        for icon_dir in update.get_all_icon_dirs(REPO_DIR):
            if not os.path.exists(icon_dir):
                os.makedirs(icon_dir)

        # Generate keystore
        pubkey, fingerprint = common.genkeystore(config)
        self.public_key = pubkey
        self.fingerprint = fingerprint.replace(" ", "")

        # Generate and save QR Code
        self._generate_qrcode()

        # Generate repository website
        self._generate_page()

        self.save()

    def _generate_qrcode(self):
        # delete QR code if we don't have a repo URL at the moment
        if not self.get_mobile_url():
            self.qrcode.delete(save=False)
            return

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=4,
        )
        qr.add_data(self.get_mobile_url())
        qr.make(fit=True)
        img = qr.make_image()

        # save in database/media location
        f = BytesIO()
        try:
            if self.qrcode:
                self.qrcode.delete(save=False)
            img.save(f, format='png')
            self.qrcode.save('qrcode.png', ContentFile(f.getvalue()), False)
        finally:
            f.close()

    def _generate_page(self):
        if not self.get_fingerprint_url():
            return

        # Render page to string
        repo_page_string = render_to_string('maker/repo_page/index.html', {'repo': self})
        repo_page_string = repo_page_string.replace('/static/maker/css/', '')

        # Render qr_code page to string
        qr_page_string = render_to_string('maker/repo_page/qr_code.html', {'repo': self})
        qr_page_string = qr_page_string.replace('/static/maker/css/', '')

        with open(os.path.join(self.get_repo_path(), 'index.html'), 'w') as f:
            f.write(repo_page_string)  # Write repo page to file

        with open(os.path.join(self.get_repo_path(), 'qr_code.html'), 'w') as f:
            f.write(qr_page_string)  # Write repo qr page to file

        # copy page assets
        self._copy_page_assets()

    def _copy_page_assets(self):
        """
        Copies various assets required for the repo page.
        """
        files = [
            # MDL JavaScript dependency
            (os.path.join(settings.NODE_MODULES_ROOT, 'material-design-lite', 'material.min.js'),
             os.path.join(self.get_repo_path(), 'material.min.js')),
            # Stylesheet
            (os.path.join(settings.STATIC_ROOT, 'maker', 'css', 'repo_page.css'),
             os.path.join(self.get_repo_path(), 'repo_page.css')),
        ]

        # Ensure Roboto fonts path exists
        roboto_font_path = os.path.join(self.get_repo_path(), 'roboto-fonts', 'Roboto')
        if not os.path.exists(roboto_font_path):
            os.makedirs(roboto_font_path)

        # Add the three needed fonts from Roboto to files
        roboto_fonts = ['Roboto-Bold.woff2', 'Roboto-Medium.woff2', 'Roboto-Regular.woff2']
        for font in roboto_fonts:
            source = os.path.join(settings.NODE_MODULES_ROOT, 'roboto-fontface', 'fonts', 'Roboto',
                                  font)
            target = os.path.join(roboto_font_path, font)
            files.append((source, target))

        # Add page graphic assets to files
        icons = ['f-droid.png', 'twitter.png', 'facebook.png']
        icon_path = os.path.join(settings.BASE_DIR, 'maker', 'static', 'maker', 'images',
                                 'repo_page')
        for icon in icons:
            source = os.path.join(icon_path, icon)
            target = os.path.join(self.get_repo_path(), icon)
            files.append((source, target))

        # Copy all files
        for source, target in files:
            copy(source, target)

    def set_url(self, url):
        self.url = url
        self._generate_qrcode()
        self._generate_page()
        self.save()

    def update_async(self):
        """
        Schedules the repository to be updated (and published)
        """
        if self.update_scheduled:
            return  # no need to update a repo twice with same data
        self.update_scheduled = True
        self.save()
        tasks.update_repo(self.id)

    def update(self):
        """
        Updates the repository on disk, generates index, categories, etc.

        You normally don't need to call this directly
        as it is meant to be run in a background task scheduled by update_async().
        """
        from maker.models.storage import StorageManager
        self.chdir()
        config = self.get_config()
        StorageManager.add_to_config(self, config)

        # ensure that this repo's main URL is set prior to updating
        if not self.url and len(config['mirrors']) > 0:
            self.set_url(config['mirrors'][0])

        # Gather information about all the apk files in the repo directory, using
        # cached data if possible.
        apkcache = update.get_cache()

        # Scan all apks in the main repo
        knownapks = common.KnownApks()
        apks, cachechanged = update.scan_apks(apkcache, REPO_DIR, knownapks, False)

        # Apply app metadata from database
        apps = {}
        categories = set()
        for apk in apks:
            try:
                from maker.models.app import App
                app = App.objects.get(repo=self, package_id=apk['packageName']).to_metadata_app()
                apps[app.id] = app
                categories.update(app.Categories)
            except ObjectDoesNotExist:
                logging.warning("App '%s' not found in database", apk['packageName'])

        update.apply_info_from_latest_apk(apps, apks)

        # Sort the app list by name
        sortedids = sorted(apps.keys(), key=lambda app_id: apps[app_id].Name.upper())

        # Make the index for the repo
        index.make(apps, sortedids, apks, REPO_DIR, False)
        update.make_categories_txt(REPO_DIR, categories)

        # Update cache if it changed
        if cachechanged:
            update.write_cache(apkcache)

        # Update page
        self._generate_page()

    def publish(self):
        """
        Publishes the repository to the available storage locations

        You normally don't need to call this manually
        as it is intended to be called automatically after each update.
        """
        from maker.models.storage import StorageManager
        remote_storage = StorageManager.get_storage(self, onlyEnabled=True)
        if len(remote_storage) == 0:
            return  # bail out if there is no remote storage to publish to

        # Publish to remote storage
        self.chdir()  # expected by server.update_awsbucket()
        for storage in remote_storage:
            storage.publish()

        # Update the publication date
        self.last_publication_date = timezone.now()

    class Meta(AbstractRepository.Meta):
        verbose_name_plural = "Repositories"


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
        tasks.update_remote_repo(self.id, repeat=Task.DAILY)

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
        if update_apps:  # TODO improve this once the workflow has been designed
            self.index_etag = etag  # don't set etag when only adding the repo, so it fetches again
        self._update(repo_index, update_apps)  # also saves at the end

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
        url = self.url + '/' + icon_name
        icon, etag = net.http_get(url, self.icon_etag)
        if icon is None:
            return  # icon did not change
        if not self.pk:
            self.save()  # to ensure the primary key exists, to be used for the file path
        self.delete_old_icon()
        self.icon_etag = etag
        self.icon.save(icon_name, BytesIO(icon), save=False)

    def _update_apps(self, apps, packages):
        from maker.models.app import RemoteApp
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
            apk = Apk.from_json(package_info)
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
        from maker.models.app import RemoteApp
        old_apps = RemoteApp.objects.filter(repo=self).exclude(package_id__in=packages)
        if old_apps.exists():
            for app in old_apps.all():
                app.delete()

    class Meta(AbstractRepository.Meta):
        verbose_name_plural = "Remote Repositories"


@receiver(user_signed_up)
def after_user_signed_up(**kwargs):
    # add new user to all pre-installed repositories
    user = kwargs['user']
    for remote_repo in RemoteRepository.objects.filter(pre_installed=True).all():
        remote_repo.users.add(user)


class Options:
    verbose = settings.DEBUG
    pretty = settings.DEBUG
    quiet = not settings.DEBUG
    clean = False
    nosign = False
    no_checksum = False
    identity_file = None
    delete_unknown = False
