import logging
import os
from io import BytesIO
from shutil import copy, rmtree

import qrcode
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from fdroidserver import common, index, server, update
from repomaker import tasks
from repomaker.storage import REPO_DIR, get_repo_file_path, get_repo_root_path, \
    get_icon_file_path
from repomaker.tasks import PRIORITY_REPO

REPO_DEFAULT_ICON = os.path.join('repomaker', 'images', 'default-repo-icon.png')


class AbstractRepository(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    url = models.URLField(max_length=2048, blank=True, null=True)
    icon = models.ImageField(upload_to=get_icon_file_path)
    public_key = models.TextField(blank=True)
    fingerprint = models.CharField(max_length=512, blank=True)
    update_scheduled = models.BooleanField(default=False)
    is_updating = models.BooleanField(default=False)
    last_updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name

    @property
    def icon_url(self):
        if self.icon:
            return self.icon.url
        return static(REPO_DEFAULT_ICON)

    def get_path(self):
        raise NotImplementedError()

    def get_repo_path(self):
        return os.path.join(self.get_path(), REPO_DIR)

    def get_fingerprint_with_spaces(self):
        fingerprint = str()
        # noinspection PyTypeChecker
        for i in range(0, int(len(self.fingerprint) / 2)):
            fingerprint += self.fingerprint[i * 2:i * 2 + 2] + ' '
        return fingerprint.rstrip()

    def get_fingerprint_url(self):
        if not self.url:
            return None
        return self.url + "?fingerprint=" + self.fingerprint

    def get_mobile_url(self):
        if not self.get_fingerprint_url():
            return None
        return self.get_fingerprint_url().replace('http', 'fdroidrepo', 1)

    def delete_old_icon(self):
        if self.icon:
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
            'repo_description': self.description,
            'repo_keyalias': 'Key Alias',
            'keydname': 'CN=repomaker.f-droid.org, OU=F-Droid',
            'keystore': os.path.join(self.get_private_path(), 'keystore.jks'),
            'keystorepass': self.key_store_pass,
            'keypass': self.key_pass,
            'nonstandardwebroot': True,  # TODO remove this when storage URLs are standardized
        })
        if self.icon:
            config['repo_icon'] = self.icon.name
        else:
            config['repo_icon'] = os.path.join(settings.BASE_DIR, 'repomaker', 'static',
                                               REPO_DEFAULT_ICON)
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

        Because some keystore types (e.g. PKCS12) don't support
        different passwords for store and key,
        we give them the same password.
        We still treat them differently to support former versions
        of Repomaker which used different passwords but
        did not work with all types of keystores.
        """
        self.key_store_pass = common.genpassword()
        self.key_pass = self.key_store_pass

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
            self.qrcode.save('assets/qrcode.png', ContentFile(f.getvalue()), False)
        finally:
            f.close()

    def _generate_page(self):
        if not self.get_fingerprint_url():
            return

        # Render page to string
        repo_page_string = render_to_string('repomaker/repo_page/index.html', {'repo': self})
        repo_page_string = repo_page_string.replace('/static/repomaker/css/repo/', 'assets/')

        # Render qr_code page to string
        qr_page_string = render_to_string('repomaker/repo_page/qr_code.html', {'repo': self})
        qr_page_string = qr_page_string.replace('/static/repomaker/css/repo/', '')

        with open(os.path.join(self.get_repo_path(), 'index.html'), 'w', encoding='utf8') as f:
            f.write(repo_page_string)  # Write repo page to file

        repo_page_assets = os.path.join(self.get_repo_path(), 'assets')
        if not os.path.exists(repo_page_assets):
            os.makedirs(repo_page_assets)

        with open(os.path.join(repo_page_assets, 'qr_code.html'), 'w', encoding='utf8') as f:
            f.write(qr_page_string)  # Write repo qr page to file

        # copy page assets
        self._copy_page_assets()

    def _copy_page_assets(self):
        """
        Copies various assets required for the repo page.
        """
        repo_page_assets = os.path.join(self.get_repo_path(), 'assets')
        files = [
            # MDL JavaScript dependency
            (os.path.join(settings.NODE_MODULES_ROOT, 'material-design-lite', 'material.min.js'),
             os.path.join(repo_page_assets, 'material.min.js')),
            # Stylesheet
            (os.path.join(settings.STATIC_ROOT, 'repomaker', 'css', 'repo', 'page.css'),
             os.path.join(repo_page_assets, 'page.css')),
        ]

        # Ensure Roboto fonts path exists
        roboto_font_path = os.path.join(repo_page_assets, 'roboto-fonts', 'roboto')
        if not os.path.exists(roboto_font_path):
            os.makedirs(roboto_font_path)

        # Add the three needed fonts from Roboto to files
        roboto_fonts = ['Roboto-Bold.woff2', 'Roboto-Medium.woff2', 'Roboto-Regular.woff2']
        for font in roboto_fonts:
            source = os.path.join(settings.NODE_MODULES_ROOT, 'roboto-fontface', 'fonts', 'roboto',
                                  font)
            target = os.path.join(roboto_font_path, font)
            files.append((source, target))

        # Add page graphic assets to files
        icons = ['f-droid.png', 'twitter.png', 'facebook.png']
        icon_path = os.path.join(settings.BASE_DIR, 'repomaker', 'static', 'repomaker', 'images',
                                 'repo_page')
        for icon in icons:
            source = os.path.join(icon_path, icon)
            target = os.path.join(repo_page_assets, icon)
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
        tasks.update_repo(self.id, priority=PRIORITY_REPO)  # pylint: disable=unexpected-keyword-arg

    def update(self):
        """
        Updates the repository on disk, generates index, categories, etc.

        You normally don't need to call this directly
        as it is meant to be run in a background task scheduled by update_async().
        """
        from repomaker.models import App, ApkPointer
        from repomaker.models.storage import StorageManager
        self.chdir()
        config = self.get_config()
        StorageManager.add_to_config(self, config)

        # ensure that this repo's main URL is set prior to updating
        if not self.url and len(config['mirrors']) > 0:
            self.set_url(config['mirrors'][0])

        # Gather information about all the apk files in the repo directory, using
        # cached data if possible.
        apkcache = update.get_cache()

        # Process all apks in the main repo
        knownapks = common.KnownApks()
        apks, cache_changed = update.process_apks(apkcache, REPO_DIR, knownapks, False)

        # Apply app metadata from database
        apps = {}
        categories = set()
        for apk in apks:
            try:
                app = App.objects.get(repo=self, package_id=apk['packageName']).to_metadata_app()
                apps[app.id] = app
                categories.update(app.Categories)
            except ObjectDoesNotExist:
                logging.warning("App '%s' not found in database", apk['packageName'])

        # Scan non-apk files in the repo
        files, file_cache_changed = update.scan_repo_files(apkcache, REPO_DIR, knownapks, False)

        # Apply metadata from database
        for file in files:
            pointers = ApkPointer.objects.filter(repo=self, apk__hash=file['hash'])
            if not pointers.exists():
                logging.warning("App with hash '%s' not found in database", file['hash'])
            elif pointers.count() > 1:
                logging.error("Repo %d has more than one app with hash '%s'", self.pk, file['hash'])
            else:
                # add app to list of apps to be included in index
                pointer = pointers[0]
                app = pointer.app.to_metadata_app()
                apps[pointer.app.package_id] = app
                categories.update(app.Categories)

                # update package data and add to repo files
                file['name'] = pointer.app.name
                file['versionCode'] = pointer.apk.version_code
                file['versionName'] = pointer.apk.version_name
                file['packageName'] = pointer.apk.package_id
                apks.append(file)

        update.apply_info_from_latest_apk(apps, apks)

        # Sort the app list by name
        sortedids = sorted(apps.keys(), key=lambda app_id: apps[app_id].Name.upper())

        # Make the index for the repo
        index.make(apps, sortedids, apks, REPO_DIR, False)
        update.make_categories_txt(REPO_DIR, categories)

        # Update cache if it changed
        if cache_changed or file_cache_changed:
            update.write_cache(apkcache)

        # Update repo page
        self._generate_page()

    def publish(self):
        """
        Publishes the repository to the available storage locations

        You normally don't need to call this manually
        as it is intended to be called automatically after each update.
        """
        from repomaker.models.storage import StorageManager
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


@receiver(post_delete, sender=Repository)
def repository_post_delete_handler(**kwargs):
    repo = kwargs['instance']
    logging.info("Deleting Repo: %s", repo.name)
    repo_local_path = repo.get_path()
    if os.path.exists(repo_local_path):
        rmtree(repo_local_path)
    repo_private_path = repo.get_private_path()
    if os.path.exists(repo_private_path):
        rmtree(repo_private_path)


class Options:
    verbose = settings.DEBUG
    pretty = settings.DEBUG
    quiet = not settings.DEBUG
    clean = False
    nosign = False
    no_checksum = False
    identity_file = None
    delete_unknown = False
    rename_apks = False
    allow_disabled_algorithms = False
    no_keep_git_mirror_archive = True
