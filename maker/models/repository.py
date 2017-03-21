import logging
import os
import pickle
from io import BytesIO

import qrcode
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.db import models
from django.forms import ModelForm
from django.utils import timezone
from fdroidserver import common
from fdroidserver import server
from fdroidserver import update

from maker.storage import REPO_DIR
from maker.storage import get_media_file_path, get_repo_path

keydname = "CN=localhost.localdomain, OU=F-Droid"

# less than the valid range of versionCode, i.e. Java's Integer.MIN_VALUE
UNSET_VERSION_CODE = -0x100000000


class Repository(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField()
    url = models.URLField(max_length=2048)
    icon = models.ImageField(upload_to=get_media_file_path, default=settings.REPO_DEFAULT_ICON)
    # TODO cache pubkey here
    fingerprint = models.CharField(max_length=512, blank=True)
    qrcode = models.ImageField(upload_to=get_media_file_path, blank=True)
    created_date = models.DateTimeField(default=timezone.now)
    last_updated_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_path(self):
        return os.path.join(settings.REPO_ROOT, get_repo_path(self))

    def get_repo_path(self):
        return os.path.join(self.get_path(), REPO_DIR)

    def get_fingerprint_url(self):
        return self.url + "?fingerprint=" + self.fingerprint

    def get_config(self):
        # Setup config
        config = {
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
            # TODO 'repo_pubkey': repo.pubkey
        }
        common.fill_config_defaults(config)
        common.config = config
        common.options = Options
        update.config = config
        update.options = Options
        server.config = config
        server.options = Options
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
        This also sets the fingerprint for :param repo.
        """
        self.chdir()
        config = self.get_config()

        # Ensure icon directories exist
        for icon_dir in update.get_all_icon_dirs(REPO_DIR):
            if not os.path.exists(icon_dir):
                os.makedirs(icon_dir)

        # Generate keystore
        if not os.path.exists(config['keystore']):
            common.genkeystore(config)

        # Extract and save fingerprint
        # TODO improve upstream
        update.extract_pubkey()
        self.fingerprint = update.repo_pubkey_fingerprint.replace(" ", "")

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

    def update(self):
        self.chdir()
        self.get_config()

        # Gather information about all the apk files in the repo directory, using
        # cached data if possible.
        apkcachefile = os.path.join('tmp', 'apkcache')
        if os.path.exists(apkcachefile):
            with open(apkcachefile, 'rb') as cf:
                apkcache = pickle.load(cf, encoding='utf-8')
            if apkcache.get("METADATA_VERSION") != update.METADATA_VERSION:
                apkcache = {}
        else:
            apkcache = {}

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

        # Some information from the apks needs to be applied up to the application
        # level. When doing this, we use the info from the most recent version's apk.
        # We deal with figuring out when the app was added and last updated at the
        # same time.
        for appid, app in apps.items():
            bestver = UNSET_VERSION_CODE
            for apk in apks:
                if apk['packageName'] == appid:
                    if apk['versionCode'] > bestver:
                        bestver = apk['versionCode']
                        bestapk = apk
                    if 'added' in apk:
                        if not app.added or apk['added'] < app.added:
                            app.added = apk['added']
                        if not app.lastUpdated or apk['added'] > app.lastUpdated:
                            app.lastUpdated = apk['added']

            if not app.added:
                logging.debug("Don't know when " + appid + " was added")
            if not app.lastUpdated:
                logging.debug("Don't know when " + appid + " was last updated")

            if bestver == UNSET_VERSION_CODE:
                if app.Name is None:
                    app.Name = app.AutoName or appid
                app.icon = None
                logging.debug("Application " + appid + " has no packages")
            else:
                if app.Name is None:
                    app.Name = bestapk['name']
                app.icon = bestapk['icon'] if 'icon' in bestapk else None
                if app.CurrentVersionCode is None:
                    app.CurrentVersionCode = str(bestver)

        # Sort the app list by name
        sortedids = sorted(apps.keys(), key=lambda app_id: apps[app_id].Name.upper())

        # Make the index for the repo
        update.make_index(apps, sortedids, apks, REPO_DIR, False)
        update.make_categories_txt(REPO_DIR, categories)

        # Update cache if it changed
        if cachechanged:
            cache_path = os.path.dirname(apkcachefile)
            if not os.path.exists(cache_path):
                os.makedirs(cache_path)
            apkcache["METADATA_VERSION"] = update.METADATA_VERSION
            with open(apkcachefile, 'wb') as cf:
                pickle.dump(apkcache, cf)

        self.save()

    def publish(self):
        # TODO SSH/SFTP upload
        # local = self.get_repo_path()
        # remote = "user@host:/home/user/www/path/to/fdroid/"

        self.chdir()  # expected by server.update_awsbucket()
        from maker.models.s3storage import S3Storage
        for storage in S3Storage.objects.filter(repo=self):
            storage.publish()

    class Meta:
        verbose_name_plural = "Repositories"


class RepositoryForm(ModelForm):
    class Meta:
        model = Repository
        fields = ['name', 'description', 'url', 'icon']
        labels = {
            'url': 'Main URL',
        }
        help_texts = {
            'url': 'This is the primary location where your repository will be made available.',
        }


class Options:
    verbose = True
    clean = False
    nosign = False
    pretty = True
    no_checksum = False
    quiet = False
    identity_file = None
