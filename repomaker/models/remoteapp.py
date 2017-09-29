import datetime
import logging
from io import BytesIO

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from fdroidserver import net
from hvad.models import TranslatedFields

from repomaker import tasks
from repomaker.tasks import PRIORITY_REMOTE_APP_ICON
from repomaker.utils import clean
from .app import AbstractApp
from .category import Category
from .remoterepository import RemoteRepository


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
        Updates the data for this app and ensures that at least one translation exists.
        :param app: A JSON app object from the repository v1 index.
        :return: True if app changed, False otherwise
        """
        if 'lastUpdated' not in app:
            logging.warning("App %s is missing 'lastUpdated' in index")
            return False

        # don't update if app hasn't changed since last update
        last_update = datetime.datetime.fromtimestamp(app['lastUpdated'] / 1000, timezone.utc)
        if self.last_updated_date and self.last_updated_date >= last_update:
            logging.info("Skipping update of %s, because did not change.", self)
            return False
        else:
            self.last_updated_date = last_update

        if 'name' not in app:
            logging.warning("App %s is missing 'name' in index")
            return False
        self.name = app['name']
        if 'summary' in app and not self._move_to_localized(app, 'summary'):
            self.summary_override = app['summary']
        if 'description' in app and not self._move_to_localized(app, 'description'):
            self.description_override = clean(app['description'])
        if 'authorName' in app:
            self.author_name = app['authorName']
        if 'webSite' in app:
            self.website = app['webSite']
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
        if len(self.get_available_languages()) == 0:
            # no localization available, translate in default language
            self.default_translate()
            self.save()
        # do the icon last, because we require the app to be saved, so a pk exists
        if 'icon' in app:
            # Schedule icon updating task, because it takes too long within this task
            # pylint: disable=unexpected-keyword-arg
            tasks.update_remote_app_icon(self.pk, app['icon'], priority=PRIORITY_REMOTE_APP_ICON)
        return True

    @staticmethod
    def _move_to_localized(app, key):
        """
        Moves :param key into JSON localized object if possible.
        :param app: A JSON app object from the repository v1 index.
        :return: True if key could be moved, False otherwise.
        """
        if 'localized' not in app:
            app['localized'] = dict()
        if settings.LANGUAGE_CODE not in app['localized']:
            app['localized'][settings.LANGUAGE_CODE] = dict()
        if key not in app['localized'][settings.LANGUAGE_CODE]:
            # cleaning not required here, because it will be done when importing localized
            app['localized'][settings.LANGUAGE_CODE][key] = app[key]
            del app[key]
            return True
        return False

    def update_icon(self, icon_name):
        """
        Updates the app's icon from the remote repository.
        Should be run in a background task.

        :param icon_name: The file name of the icon
        """
        url = self.repo.url + '/icons-640/' + icon_name
        icon, etag = net.http_get(url, self.icon_etag)
        if icon is None:
            return  # icon did not change

        self.delete_old_icon()
        self.icon_etag = etag
        self.icon.save(icon_name, BytesIO(icon), save=True)

        # update icons of all local apps tracking this one
        for tracking_app in self.app_set.all():
            tracking_app.update_icon(self.icon)

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
        for original_language_code, translation in localized.items():
            if set(supported_fields).isdisjoint(translation.keys()):
                continue  # no supported fields in translation
            # store language code in lower-case, because in Django they are all lower-case as well
            language_code = original_language_code.lower()
            # TODO not only add, but also remove old translations again
            if language_code in available_languages:
                # we need to retrieve the existing translation
                app = RemoteApp.objects.language(language_code).get(pk=self.pk)
                app.apply_translation(original_language_code, translation)
            else:
                # create a new translation
                self.translate(language_code)
                self.apply_translation(original_language_code, translation)

    # pylint: disable=attribute-defined-outside-init
    # noinspection PyAttributeOutsideInit
    def apply_translation(self, original_language_code, translation):
        # textual metadata
        if 'summary' in translation:
            self.summary = translation['summary']
        if 'description' in translation:
            self.description = clean(translation['description'])
        # graphic assets
        url = self._get_base_url(original_language_code)
        if 'featureGraphic' in translation:
            self.feature_graphic_url = url + translation['featureGraphic']
        if 'icon' in translation:
            self.high_res_icon_url = url + translation['icon']
        if 'tvBanner' in translation:
            self.tv_banner_url = url + translation['tvBanner']
        self.save()

    def _update_screenshots(self, localized):
        from repomaker.models import RemoteScreenshot
        for original_language_code, types in localized.items():
            # store language code in lower-case, because in Django they are all lower-case as well
            language_code = original_language_code.lower()
            for t, files in types.items():
                type_url = self._get_base_url(original_language_code, t)
                # TODO not only add, but also remove old screenshots again
                # add screenshot (ignores unsupported types such as summary)
                RemoteScreenshot.add(language_code, t, self, type_url, files)

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
        from .app import App
        from .screenshot import RemoteScreenshot
        if self.is_in_repo(repo):
            raise ValidationError(_("This app does already exist in your repository."))

        # add only latest APK
        remote_pointer = self.get_latest_apk_pointer()
        if remote_pointer is None:
            raise ValidationError(_("This app does not have any working versions available."))

        # create new local app and update its information from remote app
        app = App(repo=repo, package_id=self.package_id, tracked_remote=self)
        app.update_from_tracked_remote_app(remote_pointer)

        # since this is the initial import, also add the app icon
        if self.icon:
            app.update_icon(self.icon)

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
        from .app import App
        return App.objects.filter(repo=repo, package_id=self.package_id).exists()


@receiver(post_delete, sender=RemoteApp)
def remote_app_post_delete_handler(**kwargs):
    app = kwargs['instance']
    app.delete_old_icon()
