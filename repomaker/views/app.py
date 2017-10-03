import logging
import re

import os
from django.conf import settings
from django.db.models import Q
from django.forms import FileField, ImageField, ClearableFileInput, CharField
from django.http import HttpResponseRedirect, HttpResponseServerError, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import formats
from django.utils.translation import ugettext_lazy as _
from django.utils.translation.trans_real import language_code_re
from django.views.generic import DetailView
from django.views.generic.edit import DeleteView
from hvad.forms import translatable_modelform_factory, \
    TranslatableModelForm
from hvad.views import TranslatableUpdateView
from tinymce.widgets import TinyMCE

from repomaker.models import App, ApkPointer, Screenshot
from repomaker.models.category import Category
from repomaker.models.screenshot import PHONE
from . import DataListTextInput, LanguageMixin
from .repository import RepositoryAuthorizationMixin, ApkUploadMixin


class MDLTinyMCE(TinyMCE):
    """
    Ugly hack to work around a conflict between MDL and TinyMCE. See #31 for more details.
    Also removes the requirement for language packs.
    """

    def get_mce_config(self, attrs):
        mce_config = super().get_mce_config(attrs)
        if 'language' in mce_config:
            # remove language, so no language pack will be loaded
            del mce_config['language']
        return mce_config

    def _media(self):
        # we include this manually, so we can decide what gets compressed and what not
        return ()

    media = property(_media)


class AppDetailView(RepositoryAuthorizationMixin, LanguageMixin, DetailView):
    model = App
    pk_url_kwarg = 'app_id'
    context_object_name = 'app'
    template_name = 'repomaker/app/index.html'

    def get_repo(self):
        return self.get_object().repo

    def get_queryset(self):
        return self.model.objects.language(self.get_language()).fallbacks().all()

    def get_context_data(self, **kwargs):
        context = super(AppDetailView, self).get_context_data(**kwargs)
        app = context['app']
        context['screenshots'] = Screenshot.objects.filter(app=app, type=PHONE,
                                                           language_code=self.get_language())
        context['apks'] = ApkPointer.objects.filter(app=app).order_by('-apk__version_code')
        return context

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.language_code != self.get_language():
            return redirect(obj)
        return super().get(request, *args, **kwargs)


class AppForm(TranslatableModelForm):
    screenshots = ImageField(required=False, widget=ClearableFileInput(attrs={'multiple': True}))
    apks = FileField(required=False, widget=ClearableFileInput(attrs={'multiple': True}))

    def __init__(self, *args, **kwargs):
        super(AppForm, self).__init__(*args, **kwargs)
        if self.instance.category:
            # Show only own and default categories
            self.fields['category'].queryset = Category.objects.filter(
                Q(user=None) | Q(user=self.instance.repo.user))

    def save(self, commit=True):
        # remove old feature graphic if there was one
        if 'feature_graphic' in self.initial and self.initial['feature_graphic'].name \
                and 'feature_graphic' in self.changed_data:
            old_graphic = self.initial['feature_graphic'].path
            if os.path.exists(old_graphic):
                os.remove(old_graphic)
        return super().save(commit)

    class Meta:
        model = App
        fields = ['summary', 'summary_override', 'description', 'description_override',
                  'author_name', 'website', 'category', 'screenshots', 'feature_graphic', 'apks']
        widgets = {'description': MDLTinyMCE(), 'description_override': MDLTinyMCE()}


class AppEditView(ApkUploadMixin, LanguageMixin, TranslatableUpdateView):
    model = App
    object = None
    pk_url_kwarg = 'app_id'
    context_object_name = 'app'
    template_name = 'repomaker/app/edit.html'

    def get_repo(self):
        return self.get_object().repo

    def get_form_class(self):
        return translatable_modelform_factory(self.get_language(), self.model, AppForm)

    def get_queryset(self):
        # no fallbacks here, returns 404 if language does not exist
        return self.model.objects.language(self.get_language()).all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['screenshots'] = Screenshot.objects.filter(app=self.get_object(),
                                                           type=PHONE,
                                                           language_code=self.get_language())
        context['apks'] = ApkPointer.objects.filter(app=self.object).order_by('-apk__version_code')
        if self.get_object().tracked_remote:
            # do not allow edits as long as a remote app is tracked
            self.template_name = 'repomaker/app/edit_blocked.html'
        return context

    def post(self, request, *args, **kwargs):
        if 'apks' in self.request.FILES:
            app = self.get_object()
            added_apks = self.add_apks(app)
            if len(added_apks['failed']) > 0:
                if self.request.is_ajax():
                    return HttpResponseServerError(self.get_error_msg(added_apks['failed']))
                self.object = app
                form = self.get_form()
                form.add_error('apks', self.get_error_msg(added_apks['failed']))
                return self.form_invalid(form)
            if self.request.is_ajax():
                apk_objects = added_apks['apks']
                apks = []
                for apk in apk_objects:
                    apk_dict = {
                        'id': ApkPointer.objects.get(app=app, apk=apk).id,
                        'version': _('Version %(version)s (%(code)s)') % {
                            'version': apk.version_name,
                            'code': apk.version_code
                        },
                        'released': _('Released %(date)s') % {
                            'date': formats.date_format(apk.added_date, 'DATE_FORMAT'),
                        }
                    }
                    apks.append(apk_dict)
                json_response = {
                    'repo': self.get_repo().id,
                    'app': app.id,
                    'apks': apks
                }
                return JsonResponse(json_response, safe=False)
            return super().post(request, args, kwargs)
        if 'HTTP_RM_BACKGROUND_TYPE' in request.META:
            if request.META['HTTP_RM_BACKGROUND_TYPE'] == 'screenshots':
                try:
                    screenshots = self.add_screenshots()
                except Exception as e:
                    logging.error(e)
                    return HttpResponseServerError(e)
                self.get_repo().update_async()  # schedule repository update
                json_response = {
                    'repo': self.get_repo().id,
                    'app': self.get_object().id,
                    'screenshots': screenshots
                }
                return JsonResponse(json_response, safe=False)
            if request.META['HTTP_RM_BACKGROUND_TYPE'] == 'feature-graphic':
                try:
                    graphic = self.request.FILES.getlist('feature-graphic')[0]
                    self.object = self.get_object()
                    if self.object.feature_graphic and os.path.exists(
                            self.object.feature_graphic.path):
                        os.remove(self.object.feature_graphic.path)
                    self.object.feature_graphic = graphic
                    self.object.save()
                except Exception as e:
                    logging.error(e)
                    return HttpResponseServerError(e)
                self.get_repo().update_async()  # schedule repository update
                json_response = {
                    'repo': self.get_repo().id,
                    'app': self.get_object().id,
                    'feature-graphic': self.object.feature_graphic.url
                }
                return JsonResponse(json_response, safe=False)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        if 'disable-app-tracking' in form.data:
            app = self.get_object()
            app.tracked_remote = None
            app.save()
            return HttpResponseRedirect(app.get_edit_url())
        else:
            result = super().form_valid(form)  # this saves the App
            self.add_screenshots()
            form.instance.repo.update_async()  # schedule repository update
            return result

    def add_screenshots(self):
        """
        Adds screenshots to an app.
        :return: Array with information about screenshots
        """
        screenshots = []
        for screenshot in self.request.FILES.getlist('screenshots'):
            screenshot = Screenshot.objects.create(app=self.get_object(), file=screenshot,
                                                   language_code=self.get_language())
            screenshot = {
                'id': screenshot.id,
                'url': screenshot.file.url
            }
            screenshots.append(screenshot)
        return screenshots


class AppTranslationCreateForm(AppForm):

    def __init__(self, *args, **kwargs):
        super(AppTranslationCreateForm, self).__init__(*args, **kwargs)
        self.fields['lang'] = CharField(required=True, min_length=2,
                                        widget=DataListTextInput(settings.LANGUAGES))

    def clean_lang(self):
        lang = self.cleaned_data['lang'].lower()
        if not re.match(language_code_re, lang):
            self._errors['lang'] = _('This is not a valid language code.')
        if lang in self.instance.get_available_languages():
            self._errors['lang'] = _('This language already exists. Please choose another one!')
        return lang


class AppTranslationCreateView(AppEditView):
    template_name = 'repomaker/app/translation_add.html'

    def get_queryset(self):
        return self.model.objects.all()

    def get_form_class(self):
        return AppTranslationCreateForm

    def form_valid(self, form):
        self.object.translate(form.cleaned_data['lang'])
        return super().form_valid(form)


class AppDeleteView(RepositoryAuthorizationMixin, DeleteView):
    model = App
    pk_url_kwarg = 'app_id'
    template_name = 'repomaker/app/delete.html'

    def get_repo(self):
        return self.get_object().repo

    def get_success_url(self):
        self.get_repo().update_async()  # schedule repository update
        return reverse_lazy('repo', kwargs={'repo_id': self.kwargs['repo_id']})


class AppFeatureGraphicDeleteView(RepositoryAuthorizationMixin, DeleteView):
    model = App
    pk_url_kwarg = 'app_id'
    context_object_name = 'app'
    template_name = 'repomaker/app/feature_graphic_delete.html'

    def delete(self, request, *args, **kwargs):
        """
        Deletes the feature graphic of the app and then
        redirects to the success URL.
        """
        self.get_object().feature_graphic.delete()
        return HttpResponseRedirect(self.get_success_url())

    def get_repo(self):
        return self.get_object().repo

    def get_success_url(self):
        self.get_repo().update_async()
        return self.get_object().get_edit_url()
