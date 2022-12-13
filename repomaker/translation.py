from modeltranslation.translator import register, TranslationOptions

from repomaker.models.app import AbstractApp, App
from repomaker.models.remoteapp import RemoteApp


@register(AbstractApp)
class AbstractAppTranslationOptions(TranslationOptions):
    fields = ('summary', 'description')


@register(App)
class AppTranslationOptions(TranslationOptions):
    fields = ('feature_graphic', 'high_res_icon', 'tv_banner')


@register(RemoteApp)
class RemoteAppTranslationOptions(TranslationOptions):
    fields = (
        'feature_graphic_url', 'feature_graphic_etag', 'high_res_icon_url',
        'high_res_icon_etag', 'tv_banner_url', 'tv_banner_etag')
