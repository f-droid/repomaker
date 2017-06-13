import datetime
import logging
import os
from io import BytesIO

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.files.base import ContentFile
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from fdroidserver import metadata, net
from hvad.models import TranslatableModel, TranslatedFields

from maker import tasks
from maker.storage import get_icon_file_path_for_app, get_graphic_asset_file_path
from maker.utils import clean
from .category import Category
from .repository import Repository, RemoteRepository

APK = 'apk'
BOOK = 'book'
DOCUMENT = 'document'
IMAGE = 'image'
AUDIO = 'audio'
VIDEO = 'video'
OTHER = 'other'
TYPE_CHOICES = (
    (APK, _('APK')),
    (BOOK, _('Book')),
    (DOCUMENT, _('Document')),
    (IMAGE, _('Image')),
    (AUDIO, _('Audio')),
    (VIDEO, _('Video')),
    (OTHER, _('Other')),
)


class AbstractApp(TranslatableModel):
    package_id = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255, blank=True)
    summary = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)  # always clean and then consider safe
    author_name = models.CharField(max_length=255, blank=True)
    website = models.URLField(max_length=2048, blank=True)
    icon = models.ImageField(upload_to=get_icon_file_path_for_app,
                             default=settings.APP_DEFAULT_ICON)
    category = models.ManyToManyField(Category, blank=True, limit_choices_to={'user': None})
    added_date = models.DateTimeField(default=timezone.now)
    translations = TranslatedFields(
        # for historic reasons summary and description are also included non-localized in the index
        l_summary=models.CharField(max_length=255, blank=True, verbose_name=_("Summary")),
        l_description=models.TextField(blank=True, verbose_name=_("Description")),
    )

    def __str__(self):
        return self.name

    def get_available_language_names(self):
        """
        Returns a list of language names and uses the language code, if no name is available.
        """
        language_names = []
        for lang in self.get_available_languages():
            found_name = False
            for code, name in settings.LANGUAGES:
                if code == lang:
                    language_names.append(name)
                    found_name = True
                    break
            if not found_name:
                language_names.append(lang)
        return language_names

    def get_icon_basename(self):
        return os.path.basename(self.icon.path)

    def get_latest_version(self):
        raise NotImplementedError()

    def delete_old_icon(self):
        icon_path = os.path.dirname(self.icon.path)
        if icon_path != settings.MEDIA_ROOT:
            self.icon.delete(save=False)

    class Meta:
        abstract = True
        ordering = ['added_date']
        unique_together = (("package_id", "repo"),)


class App(AbstractApp):
    repo = models.ForeignKey(Repository, on_delete=models.CASCADE)
    type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=APK)
    last_updated_date = models.DateTimeField(auto_now=True)
    translations = TranslatedFields(
        feature_graphic=models.ImageField(blank=True, max_length=1024,
                                          upload_to=get_graphic_asset_file_path),
        high_res_icon=models.ImageField(blank=True, max_length=1024,
                                        upload_to=get_graphic_asset_file_path),
        tv_banner=models.ImageField(blank=True, max_length=1024,
                                    upload_to=get_graphic_asset_file_path),
    )

    def get_absolute_url(self):
        return reverse('app', kwargs={'repo_id': self.repo.pk, 'app_id': self.pk})

    def get_edit_url(self):
        return reverse('edit_app', kwargs={'repo_id': self.repo.pk, 'app_id': self.pk})

    def get_previous(self):
        return self.get_previous_by_added_date(repo=self.repo)

    def get_next(self):
        return self.get_next_by_added_date(repo=self.repo)

    @staticmethod
    def from_remote_app(repo, app):
        """
        Returns an App in :param repo from the given RemoteApp :param app.

        Note that it does exclude the category. You need to add these after saving the app.
        """
        # TODO check how the icon extracted to repo/icons-640 could be used instead
        icon = ContentFile(app.icon.read())
        icon.name = os.path.basename(app.icon.name)
        return App(repo=repo, package_id=app.package_id, name=app.name, summary=app.summary,
                   description=clean(app.description), website=app.website, icon=icon,
                   author_name=app.author_name)

    def to_metadata_app(self):
        meta = metadata.App()
        meta.id = self.package_id
        meta.Name = self.name
        meta.WebSite = self.website
        meta.Summary = self.summary
        meta.Description = self.description
        meta.AuthorName = self.author_name
        meta.added = timezone.make_naive(self.added_date)
        meta.Categories = [category.name for category in self.category.all()]
        meta['localized'] = self._get_screenshot_dict()
        self._add_translations_to_localized(meta['localized'])
        return meta

    def _add_translations_to_localized(self, localized):
        for language_code in self.get_available_languages():
            if language_code not in localized:
                localized[language_code] = dict()
            app = App.objects.language(language_code).get(pk=self.pk)
            if app.l_summary:
                localized[language_code]['summary'] = app.l_summary
            if app.l_description:
                localized[language_code]['description'] = app.l_description
            if app.feature_graphic:
                localized[language_code]['featureGraphic'] = os.path.basename(
                    app.feature_graphic.name)
            if app.high_res_icon:
                localized[language_code]['icon'] = os.path.basename(app.high_res_icon.name)
            if app.tv_banner:
                localized[language_code]['tvBanner'] = os.path.basename(app.tv_banner.name)

    def _get_screenshot_dict(self):
        from . import Screenshot
        localized = dict()
        screenshots = Screenshot.objects.filter(app=self).all()
        for s in screenshots:
            if s.language_code not in localized:
                localized[s.language_code] = dict()
            if s.type not in localized[s.language_code]:
                localized[s.language_code][s.type] = []
            localized[s.language_code][s.type].append(os.path.basename(s.file.name))
        return localized

    # pylint: disable=attribute-defined-outside-init
    def copy_translations_from_remote_app(self, remote_app):
        """
        Copies metadata translations from given RemoteApp.

        Attention: This requires that no translations exist so far.
        """
        for language_code in remote_app.get_available_languages():
            # get the translation for current language_code
            remote_app = RemoteApp.objects.language(language_code).get(pk=remote_app.pk)
            # copy the translation to this App instance
            self.translate(language_code)
            self.l_summary = remote_app.l_summary
            self.l_description = clean(remote_app.l_description)
            self.save()

    def download_graphic_assets_from_remote_app(self, remote_app):
        """
        Does a blocking download of the RemoteApp's graphic assets and replaces the local ones.

        Attention: This assumes that all translations exist already.
        """
        for language_code in remote_app.get_available_languages():
            # get the translation for current language_code
            app = App.objects.language(language_code).get(pk=self.pk)
            remote_app = RemoteApp.objects.language(language_code).get(pk=remote_app.pk)
            if remote_app.feature_graphic_url:
                graphic, etag = net.http_get(remote_app.feature_graphic_url,
                                             remote_app.feature_graphic_etag)
                if graphic is not None:
                    app.feature_graphic.delete()
                    graphic_name = os.path.basename(remote_app.feature_graphic_url)
                    app.feature_graphic.save(graphic_name, BytesIO(graphic), save=False)
                    remote_app.feature_graphic_etag = etag
            if remote_app.high_res_icon_url:
                graphic, etag = net.http_get(remote_app.high_res_icon_url,
                                             remote_app.high_res_icon_etag)
                if graphic is not None:
                    app.high_res_icon.delete()
                    graphic_name = os.path.basename(remote_app.high_res_icon_url)
                    app.high_res_icon.save(graphic_name, BytesIO(graphic), save=False)
                    remote_app.high_res_icon_etag = etag
            if remote_app.tv_banner_url:
                graphic, etag = net.http_get(remote_app.tv_banner_url,
                                             remote_app.tv_banner_etag)
                if graphic is not None:
                    app.tv_banner.delete()
                    graphic_name = os.path.basename(remote_app.tv_banner_url)
                    app.tv_banner.save(graphic_name, BytesIO(graphic), save=False)
                    remote_app.tv_banner_etag = etag
            app.save()
            remote_app.save()

    def get_latest_version(self):
        from .apk import ApkPointer
        pointers = ApkPointer.objects.filter(app=self).order_by('-apk__version_code')
        if pointers.exists() and pointers[0].apk:
            return pointers[0].apk
        return None


class RemoteApp(AbstractApp):
    repo = models.ForeignKey(RemoteRepository, on_delete=models.CASCADE)
    icon_etag = models.CharField(max_length=128, blank=True, null=True)
    last_updated_date = models.DateTimeField(blank=True)
    translations = TranslatedFields(
        feature_graphic_url=models.URLField(blank=True, max_length=2048),
        feature_graphic_etag=models.CharField(max_length=128, blank=True, null=True),
        high_res_icon_url=models.URLField(blank=True, max_length=2048),
        high_res_icon_etag=models.CharField(max_length=128, blank=True, null=True),
        tv_banner_url=models.URLField(blank=True, max_length=2048),
        tv_banner_etag=models.CharField(max_length=128, blank=True, null=True),
    )

    def update_from_json(self, app):
        """
        Updates the data for this app.
        :param app: A JSON app object from the repository v1 index.
        :return: True if app changed, False otherwise
        """

        # don't update if app hasn't changed since last update
        last_update = datetime.datetime.fromtimestamp(app['lastUpdated'] / 1000, timezone.utc)
        if self.last_updated_date and self.last_updated_date >= last_update:
            logging.info("Skipping update of %s, because did not change.", self)
            return False
        else:
            self.last_updated_date = last_update

        self.name = app['name']
        if 'summary' in app:
            self.summary = app['summary']
        if 'description' in app:
            self.description = clean(app['description'])
        if 'authorName' in app:
            self.author_name = app['authorName']
        if 'webSite' in app:
            self.website = app['webSite']
        if 'icon' in app:
            self._update_icon(app['icon'])
        if 'categories' in app:
            self._update_categories(app['categories'])
        if 'added' in app:
            date_added = datetime.datetime.fromtimestamp(app['added'] / 1000, timezone.utc)
            if self.added_date > date_added:
                self.added_date = date_added
        self.save()
        if 'localized' in app:
            self._update_translations(app['localized'])
            self._update_screenshots(app['localized'])
        return True

    def _update_icon(self, icon_name):
        url = self.repo.url + '/icons-640/' + icon_name
        icon, etag = net.http_get(url, self.icon_etag)
        if icon is None:
            return  # icon did not change

        self.delete_old_icon()
        self.icon_etag = etag
        self.icon.save(icon_name, BytesIO(icon), save=False)

    def _update_categories(self, categories):
        if not self.pk:
            # we need to save before we can use a ManyToManyField
            self.save()
        for category in categories:
            try:
                cat = Category.objects.get(name=category)
                # TODO not only add, but also remove old categories again
                self.category.add(cat)
            except ObjectDoesNotExist:
                # Drop the unknown category, don't create new categories automatically here
                pass

    def _update_translations(self, localized):
        # TODO also support 'name, 'whatsNew' and 'video'
        supported_fields = ['summary', 'description', 'featureGraphic', 'icon', 'tvBanner']
        available_languages = self.get_available_languages()
        for language_code, translation in localized.items():
            if set(supported_fields).isdisjoint(translation.keys()):
                continue  # no supported fields in translation
            # TODO not only add, but also remove old translations again
            if language_code in available_languages:
                # we need to retrieve the existing translation
                app = RemoteApp.objects.language(language_code).get(pk=self.pk)
                app.apply_translation(language_code, translation)
            else:
                # create a new translation
                self.translate(language_code)
                self.apply_translation(language_code, translation)

    # pylint: disable=attribute-defined-outside-init
    def apply_translation(self, language_code, translation):
        # textual metadata
        if 'summary' in translation:
            self.l_summary = translation['summary']
        if 'description' in translation:
            self.l_description = clean(translation['description'])
        # graphic assets
        url = self._get_base_url(language_code)
        if 'featureGraphic' in translation:
            self.feature_graphic_url = url + translation['featureGraphic']
        if 'icon' in translation:
            self.high_res_icon_url = url + translation['icon']
        if 'tvBanner' in translation:
            self.tv_banner_url = url + translation['tvBanner']
        self.save()

    def _update_screenshots(self, localized):
        from maker.models import RemoteScreenshot
        for locale, types in localized.items():
            for t, files in types.items():
                type_url = self._get_base_url(locale, t)
                # TODO not only add, but also remove old screenshots again
                RemoteScreenshot.add(locale, t, self, type_url, files)

    def _get_base_url(self, locale, asset_type=None):
        """
        Returns the base URL for the given locale and asset type with a trailing slash
        """
        url = self.repo.url + '/' + self.package_id + '/' + locale + '/'
        if asset_type is None:
            return url
        return url + asset_type + '/'

    def get_latest_apk_pointer(self):
        """
        Returns this app's latest RemoteApkPointer object or None if none exists.
        """
        from .apk import RemoteApkPointer
        qs = RemoteApkPointer.objects.filter(app=self).order_by('-apk__version_code').all()
        if qs.count() < 1:
            return None
        return qs[0]

    def get_latest_apk(self):
        """
        Returns this app's latest Apk object or None if none exists.
        """
        apk_pointer = self.get_latest_apk_pointer()
        if apk_pointer is None:
            return None
        return apk_pointer.apk

    def add_to_repo(self, repo):
        """
        Adds this RemoteApp to the given local repository.

        :param repo: The local repository the app should be added to
        :return: The added App object
        """
        from .apk import ApkPointer
        from .screenshot import RemoteScreenshot
        if self.is_in_repo(repo):
            raise ValidationError(_("This app does already exist in your repository."))

        # add only latest APK
        remote_pointer = self.get_latest_apk_pointer()
        if remote_pointer is None:
            raise ValidationError(_("This app does not have any working versions available."))
        apk = remote_pointer.apk

        # add app
        app = App.from_remote_app(repo, self)
        app.copy_translations_from_remote_app(self)
        app.save()
        app.category = self.category.all()
        app.save()

        # create a local pointer to the APK
        pointer = ApkPointer(apk=apk, repo=repo, app=app)
        if apk.file:
            pointer.link_file_from_apk()  # this also saves the pointer
        else:
            pointer.save()
            # schedule APK file download if necessary, also updates all local pointers to that APK
            apk.download_async(remote_pointer.url)

        # schedule download of remote graphic assets
        tasks.download_remote_graphic_assets(app.id, self.id)

        # schedule download of remote screenshots if available
        for remote in RemoteScreenshot.objects.filter(app=self).all():
            remote.download_async(app)

        return app

    def get_latest_version(self):
        from .apk import RemoteApkPointer
        pointers = RemoteApkPointer.objects.filter(app=self).order_by('-apk__version_code')
        if pointers.exists() and pointers[0].apk:
            return pointers[0].apk
        return None

    def is_in_repo(self, repo):
        """
        :param repo: A Repository object.
        :return: True if an app with this package_id is in repo, False otherwise
        """
        return App.objects.filter(repo=repo, package_id=self.package_id).exists()


@receiver(post_delete, sender=App)
def app_post_delete_handler(**kwargs):
    app = kwargs['instance']
    app.delete_old_icon()


@receiver(post_delete, sender=RemoteApp)
def remote_app_post_delete_handler(**kwargs):
    app = kwargs['instance']
    app.delete_old_icon()
