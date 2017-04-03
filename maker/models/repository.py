import datetime
import logging
import os
from io import BytesIO

import qrcode
import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.db import models
from django.urls import reverse
from django.utils import timezone
from fdroidserver import common
from fdroidserver import index
from fdroidserver import server
from fdroidserver import update

from maker.storage import REPO_DIR
from maker.storage import get_media_file_path, get_remote_repo_path, get_repo_path
from maker.tasks import update_repo

keydname = "CN=localhost.localdomain, OU=F-Droid"


class AbstractRepository(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    url = models.URLField(max_length=2048)
    icon = models.ImageField(upload_to=get_media_file_path, default=settings.REPO_DEFAULT_ICON)
    public_key = models.TextField(blank=True)
    fingerprint = models.CharField(max_length=512, blank=True)
    update_scheduled = models.BooleanField(default=False)
    is_updating = models.BooleanField(default=False)
    last_updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        unique_together = (("url", "fingerprint"),)

    def __str__(self):
        return self.name

    def get_path(self):
        raise NotImplementedError()

    def get_repo_path(self):
        return os.path.join(self.get_path(), REPO_DIR)

    def get_fingerprint_url(self):
        return self.url + "?fingerprint=" + self.fingerprint

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


class RemoteRepository(AbstractRepository):
    users = models.ManyToManyField(User)
    pre_installed = models.BooleanField(default=False)
    last_change_date = models.DateTimeField(auto_now=True)

    def get_path(self):
        return os.path.join(settings.REPO_ROOT, get_remote_repo_path(self))

    def update_index(self, update_apps=True):
        """
        Downloads the remote index and passes it to update()

        :raises: VerificationException() if the index can not be validated anymore
        """
        self.get_config()
        repo_index = index.download_repo_index(self.get_fingerprint_url())
        self._update(repo_index, update_apps)

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
            return

        # update repository's metadata
        self.name = repo_index['repo']['name']
        self.description = repo_index['repo']['description']
        self.last_change_date = repo_index['repo']['timestamp']
        if not self.public_key:
            self.public_key = repo_index['repo']['pubkey']

        # download and save repository icon
        icon_url = self.url + '/' + repo_index['repo']['icon']
        try:
            # TODO use eTag like in RemoteApp._update_icon()
            r = requests.get(icon_url)
            if r.status_code != requests.codes.ok:
                r.raise_for_status()
            self.save()  # to ensure the primary key exists, to be used for the file path
            self.delete_old_icon()
            self.icon.save(repo_index['repo']['icon'], BytesIO(r.content), save=False)
        except Exception as e:
            logging.warning("Could not download repository icon from %s. %s" % (icon_url, e))

        self.save()

        if update_apps:
            self._update_apps(repo_index['apps'])
            # TODO update apk information as well
            # repo_index['packages'])

    def _update_apps(self, apps):
        from maker.models.app import RemoteApp
        # update the apps from this repo and remember all package names we have seen
        package_names = []
        for app in apps:
            if self.pk:
                query_set = RemoteApp.objects.filter(repo__pk=self.pk,
                                                     package_id=app['packageName'])
                if query_set.exists():
                    query_set.get().update_from_json(app)
                    package_names.append(app['packageName'])
                    continue
            # app does not exist, so update it
            new_app = RemoteApp(package_id=app['packageName'], repo=self)
            new_app.update_from_json(app)
            package_names.append(app['packageName'])

        # TODO remove apps that no longer exist
        print(package_names)

    class Meta(AbstractRepository.Meta):
        verbose_name_plural = "Remote Repositories"
        unique_together = (("url", "fingerprint"),)


class Repository(AbstractRepository):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    qrcode = models.ImageField(upload_to=get_media_file_path, blank=True)
    created_date = models.DateTimeField(default=timezone.now)
    last_publication_date = models.DateTimeField(null=True, blank=True)

    def get_absolute_url(self):
        return reverse('repo', kwargs={'repo_id': self.pk})

    def get_path(self):
        return os.path.join(settings.REPO_ROOT, get_repo_path(self))

    def get_config(self):
        config = super().get_config()
        config.update({
            'repo_url': self.url,
            'repo_name': self.name,
            'repo_icon': os.path.join(settings.MEDIA_ROOT, self.icon.name),
            'repo_description': self.description,
            'repo_keyalias': "Key Alias",
            'keydname': keydname,
            'keystore': "keystore.jks",  # common.default_config['keystore'],
            'keystorepass': "uGrqvkPLiGptUScrAHsVAyNSQqyJq4OQJSiN1YZWxes=",  # common.genpassword(),
            'keystorepassfile': '.fdroid.keystorepass.txt',
            'keypass': "uGrqvkPLiGptUScrAHsVAyNSQqyJq4OQJSiN1YZWxes=",  # common.genpassword(),
            'keypassfile': '.fdroid.keypass.txt',
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
        self.generate_qrcode()

        # Generate repository website
        self.generate_page()

        self.save()

    def generate_qrcode(self):
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=4,
        )
        qr.add_data(self.get_fingerprint_url())
        qr.make(fit=True)
        img = qr.make_image()

        # save in database/media location
        f = BytesIO()
        try:
            # TODO delete old QR code if there was one
            img.save(f, format='png')
            self.qrcode.save(self.fingerprint + ".png", ContentFile(f.getvalue()), False)
        finally:
            f.close()

        # save in repo
        img.save(os.path.join(self.get_repo_path(), 'qrcode.png'), format='png')

    def generate_page(self):
        with open(os.path.join(self.get_repo_path(), 'index.html'), 'w') as file:
            file.write('<a href="%s"/>' % self.get_fingerprint_url())
            file.write('<img src="qrcode.png"/> ')
            file.write(self.get_fingerprint_url())
            file.write('</a>')

    def update_async(self):
        """
        Schedules the repository to be updated (and published)
        """
        if self.update_scheduled:
            return  # no need to update a repo twice with same data
        self.update_scheduled = True
        self.save()
        update_repo(self.id)

    def update(self):
        """
        Updates the repository on disk, generates index, categories, etc.

        You normally don't need to call this directly
        as it is meant to be run in a background task scheduled by update_async().
        """
        self.chdir()
        self.get_config()

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
                logging.warning("App '%s' not found in database" % apk['packageName'])

        update.apply_info_from_latest_apk(apps, apks)

        # Sort the app list by name
        sortedids = sorted(apps.keys(), key=lambda app_id: apps[app_id].Name.upper())

        # Make the index for the repo
        index.make(apps, sortedids, apks, REPO_DIR, False)
        update.make_categories_txt(REPO_DIR, categories)

        # Update cache if it changed
        if cachechanged:
            update.write_cache(apkcache)

    def publish(self):
        """
        Publishes the repository to the available storage locations

        You normally don't need to call this manually
        as it is intended to be called automatically after each update.
        """
        # Publish to SSH Storage
        from maker.models.sshstorage import SshStorage
        for storage in SshStorage.objects.filter(repo=self):
            storage.publish()

        # Publish to Amazon S3
        self.chdir()  # expected by server.update_awsbucket()
        from maker.models.s3storage import S3Storage
        for storage in S3Storage.objects.filter(repo=self):
            storage.publish()

        self.last_publication_date = timezone.now()

    class Meta(AbstractRepository.Meta):
        verbose_name_plural = "Repositories"


class Options:
    verbose = settings.DEBUG
    pretty = settings.DEBUG
    quiet = not settings.DEBUG
    clean = False
    nosign = False
    no_checksum = False
    identity_file = None
