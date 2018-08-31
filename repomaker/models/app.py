from io import BytesIO

import os
from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _, get_language
from fdroidserver import metadata, net
from hvad.models import TranslatableModel, TranslatedFields
from hvad.utils import load_translation

from repomaker.storage import get_icon_file_path_for_app, \
    get_graphic_asset_file_path
from repomaker.utils import clean, to_universal_language_code
from .category import Category
from .repository import Repository

APK = 'apk'
BOOK = 'book'
DOCUMENT = 'document'
IMAGE = 'image'
AUDIO = 'audio'
VIDEO = 'video'
OTHER = 'other'  # deprecated due to white-list
TYPE_CHOICES = (
    (APK, _('APK')),
    (BOOK, _('Book')),
    (DOCUMENT, _('Document')),
    (IMAGE, _('Image')),
    (AUDIO, _('Audio')),
    (VIDEO, _('Video')),
    (OTHER, _('Other')),
)
APP_DEFAULT_ICON = os.path.join('repomaker', 'images', 'default-app-icon.png')


class AbstractApp(TranslatableModel):
    package_id = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255, blank=True)
    summary_override = models.CharField(max_length=255, blank=True)
    description_override = models.TextField(blank=True)  # always clean and then consider safe
    author_name = models.CharField(max_length=255, blank=True)
    website = models.URLField(max_length=2048, blank=True)
    icon = models.ImageField(upload_to=get_icon_file_path_for_app)
    category = models.ManyToManyField(Category, blank=True, limit_choices_to={'user': None})
    added_date = models.DateTimeField(default=timezone.now)
    translations = TranslatedFields(
        # for historic reasons summary and description are also included non-localized in the index
        summary=models.CharField(max_length=255, blank=True),
        description=models.TextField(blank=True),  # always clean and then consider safe
    )

    def __str__(self):
        return self.name

    @property
    def icon_url(self):
        if self.icon:
            return self.icon.url
        return static(APP_DEFAULT_ICON)

    def default_translate(self):
        """Creates a new default translation"""
        language = get_language()
        if language is None:
            self.translate(settings.LANGUAGE_CODE)
        else:
            self.translate(language)

    def get_translation(self, language_code=get_language()):
        """
        Returns a translation of this instance for the given language_code

        A valid translation instance is always returned.
        It will be loaded from the database as required.
        If this fails, a new, empty, ready-to-use translation will be returned.
        """
        return load_translation(self, language_code, enforce=True)

    def get_available_languages_as_dicts(self):
        """
        Returns a list of dictionaries that include the language name and code
        If no name is available, it uses the language code as the name
        """
        languages = []
        for lang in self.get_available_languages():
            found_name = False
            for code, name in settings.LANGUAGES:
                if code == lang:
                    languages.append({'code': code, 'name': name})
                    found_name = True
                    break
            if not found_name:
                languages.append({'code': lang, 'name': lang})
        return languages

    def get_icon_basename(self):
        if self.icon:
            return os.path.basename(self.icon.path)
        # TODO handle default app icons on static repo page
        return None

    def get_latest_version(self):
        raise NotImplementedError()

    def delete_old_icon(self):
        if self.icon:
            self.icon.delete(save=False)

    class Meta:
        abstract = True
        ordering = ['added_date']
        unique_together = (("package_id", "repo"),)


class App(AbstractApp):
    repo = models.ForeignKey(Repository, on_delete=models.CASCADE)
    type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=APK)
    last_updated_date = models.DateTimeField(auto_now=True)
    tracked_remote = models.ForeignKey('RemoteApp', null=True, default=None,
                                       on_delete=models.SET_NULL)
    translations = TranslatedFields(
        feature_graphic=models.ImageField(blank=True, max_length=1024,
                                          upload_to=get_graphic_asset_file_path),
        high_res_icon=models.ImageField(blank=True, max_length=1024,
                                        upload_to=get_graphic_asset_file_path),
        tv_banner=models.ImageField(blank=True, max_length=1024,
                                    upload_to=get_graphic_asset_file_path),
    )

    def get_absolute_url(self):
        kwargs = {'repo_id': self.repo.pk, 'app_id': self.pk}
        try:
            kwargs['lang'] = self.language_code
        except AttributeError:
            kwargs['lang'] = self.get_available_languages()[0]
        return reverse('app', kwargs=kwargs)

    def get_edit_url(self):
        kwargs = {'repo_id': self.repo.pk, 'app_id': self.pk}
        try:
            kwargs['lang'] = self.language_code
        except AttributeError:
            kwargs['lang'] = self.get_available_languages()[0]
        return reverse('app_edit', kwargs=kwargs)

    def get_previous(self):
        return self.get_previous_by_added_date(repo=self.repo)

    def get_next(self):
        return self.get_next_by_added_date(repo=self.repo)

    def to_metadata_app(self):
        meta = metadata.App()
        meta.id = self.package_id
        meta.Name = self.name
        meta.WebSite = self.website
        meta.Summary = self.summary_override
        meta.Description = self.description_override
        meta.AuthorName = self.author_name
        meta.added = timezone.make_naive(self.added_date)
        meta.Categories = [category.name for category in self.category.all()]
        meta['localized'] = self._get_screenshot_dict()
        self._add_translations_to_localized(meta['localized'])
        return meta

    def _add_translations_to_localized(self, localized):
        for original_language_code in self.get_available_languages():
            # upper-case region part of language code for compatibility
            language_code = to_universal_language_code(original_language_code)
            if language_code not in localized:
                localized[language_code] = dict()
            app = self.get_translation(original_language_code)
            if app.summary:
                localized[language_code]['summary'] = app.summary
            if app.description:
                localized[language_code]['description'] = app.description
            if app.feature_graphic:
                localized[language_code]['featureGraphic'] = os.path.basename(
                    app.feature_graphic.name)
            if app.high_res_icon:
                localized[language_code]['icon'] = os.path.basename(app.high_res_icon.name)
            if app.tv_banner:
                localized[language_code]['tvBanner'] = os.path.basename(app.tv_banner.name)
            if localized[language_code] == {}:
                # remove empty translation
                del localized[language_code]

    def _get_screenshot_dict(self):
        from . import Screenshot
        localized = dict()
        screenshots = Screenshot.objects.filter(app=self).all()
        for s in screenshots:
            # upper-case region part of language code for compatibility
            language_code = to_universal_language_code(s.language_code)
            if language_code not in localized:
                localized[language_code] = dict()
            if s.type not in localized[language_code]:
                localized[language_code][s.type] = []
            localized[language_code][s.type].append(os.path.basename(s.file.name))
        return localized

    # pylint: disable=attribute-defined-outside-init
    # noinspection PyAttributeOutsideInit
    def copy_translations_from_remote_app(self, remote_app):
        """
        Copies metadata translations from given RemoteApp
        and ensures that at least one translation exists at the end.
        """
        from .remoteapp import RemoteApp
        for language_code in remote_app.get_available_languages():
            # get the translation for current language_code
            remote_app = RemoteApp.objects.language(language_code).get(pk=remote_app.pk)
            # copy the translation to this App instance
            if language_code in self.get_available_languages():
                app = App.objects.language(language_code).get(pk=self.pk)
                app.summary = remote_app.summary
                app.description = clean(remote_app.description)
                app.save()
            else:
                self.translate(language_code)
                self.summary = remote_app.summary
                self.description = clean(remote_app.description)
                self.save()
        # ensure that at least one translation exists
        if len(self.get_available_languages()) == 0:
            self.default_translate()
            self.save()

    def download_graphic_assets_from_remote_app(self, remote_app):
        """
        Does a blocking download of the RemoteApp's graphic assets and replaces the local ones.

        Attention: This assumes that all translations exist already.
        """
        from .remoteapp import RemoteApp
        for language_code in remote_app.get_available_languages():
            # get the translation for current language_code
            app = self.get_translation(language_code)
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

    # noinspection PyTypeChecker
    def update_from_tracked_remote_app(self, remote_apk_pointer):
        """
        Update all app information from the tracked remote app

        :param remote_apk_pointer: the latest RemoteApkPointer of the app
        """
        if not self.tracked_remote:
            raise RuntimeWarning("Trying to add an APK to an app that is not tracking a remote.")

        self.name = self.tracked_remote.name
        self.author_name = self.tracked_remote.author_name
        self.website = self.tracked_remote.website
        # the icon gets updated asynchronously later by the remote app

        if not self.pk:
            self.save()  # save before adding categories, so pk exists
        self.category = self.tracked_remote.category.all()

        self.copy_translations_from_remote_app(self.tracked_remote)

        self.add_apk_from_tracked_remote_app(remote_apk_pointer)

        self.save()

    def add_apk_from_tracked_remote_app(self, remote_apk_pointer):
        """
        Add the latest APK to this app, if it does not already exist.
        Creates an ApkPointer object as well and triggers an async download if necessary.

        :param remote_apk_pointer: the latest RemoteApkPointer of the app
        """
        # bail out if we already have the latest APK
        latest_apk = self.get_latest_version()
        if latest_apk is not None and latest_apk == remote_apk_pointer.apk:
            return

        # create a local pointer to the APK
        from .apk import ApkPointer
        apk = remote_apk_pointer.apk
        pointer = ApkPointer(apk=apk, repo=self.repo, app=self)
        if apk.file:
            pointer.link_file_from_apk()  # this also saves the pointer
        else:
            pointer.save()
            # schedule APK file download if necessary, also updates all local pointers to that APK
            apk.download_async(remote_apk_pointer.url)

    def update_icon(self, icon):
        """
        Replace the old icon of this app with a new one

        :param icon: The new icon as a File
        """
        self.delete_old_icon()
        self.icon.save(os.path.basename(icon.name), icon.file, save=True)

    def get_latest_version(self):
        from .apk import ApkPointer
        pointers = ApkPointer.objects.filter(app=self).order_by('-apk__version_code')
        if pointers.exists() and pointers[0].apk:
            return pointers[0].apk
        return None


@receiver(post_delete, sender=App)
def app_post_delete_handler(**kwargs):
    app = kwargs['instance']
    app.delete_old_icon()
