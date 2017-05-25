from django.db.models import Q
from django.forms import ModelForm, FileField, ClearableFileInput
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import ugettext_lazy as _
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from hvad.forms import translationformset_factory
from tinymce.widgets import TinyMCE

from maker.models import RemoteRepository, App, RemoteApp, ApkPointer, Screenshot
from maker.models.category import Category
from . import BaseModelForm
from .repository import RepositoryAuthorizationMixin


class ApkForm(ModelForm):
    class Meta:
        model = ApkPointer
        fields = ['file']
        labels = {
            'file': _('Select APK file for upload'),
        }


class AppCreateView(RepositoryAuthorizationMixin, CreateView):
    model = ApkPointer
    form_class = ApkForm
    template_name = "maker/app/add.html"

    def get_context_data(self, **kwargs):
        context = super(AppCreateView, self).get_context_data(**kwargs)
        context = get_app_context(context, self.kwargs, self.request.user)
        if 'remote_repo_id' in self.kwargs:
            context['apps'] = RemoteApp.objects.filter(repo__pk=self.kwargs['remote_repo_id'])
        else:
            context['apps'] = RemoteApp.objects.filter(repo__in=context['repos'])
        return context

    def form_valid(self, form):
        form.instance.repo = self.get_repo()
        pointer = form.save()  # needed to save file to disk for scanning
        try:
            pointer.initialize()
        except Exception as e:
            pointer.delete()
            raise e

        if pointer.app.summary != '':  # app did exist already, show it
            return HttpResponseRedirect(reverse('app', args=[pointer.repo.pk, pointer.app.pk]))
        return super(AppCreateView, self).form_valid(form)

    def get_success_url(self):
        # edit new app
        return reverse_lazy('edit_app', kwargs={'repo_id': self.object.repo.pk,
                                                'app_id': self.object.app.pk})


class RemoteAppSearchView(RepositoryAuthorizationMixin, ListView):
    model = RemoteApp
    context_object_name = 'apps'
    template_name = "maker/app/add.html"

    def get_queryset(self):
        if 'query' not in self.request.GET:
            return RemoteApp.objects.none()
        query = self.request.GET['query']
        return RemoteApp.objects.filter(
            Q(repo__users__id=self.request.user.id) & (
                Q(name__icontains=query) |
                Q(summary__icontains=query)
            )
        )

    def get_context_data(self, **kwargs):
        return get_app_context(super(RemoteAppSearchView, self).get_context_data(**kwargs),
                               self.kwargs, self.request.user)


def get_app_context(context, kwargs, user):
    context['repo'] = {}
    context['repo']['id'] = kwargs['repo_id']
    context['repos'] = RemoteRepository.objects.filter(users__id=user.id)
    context['categories'] = Category.objects.filter(
        Q(user=None) | Q(user=user))
    if 'remote_repo_id' in kwargs:
        context['remote_repo'] = RemoteRepository.objects.get(pk=kwargs['remote_repo_id'])
    return context


class AppDetailView(RepositoryAuthorizationMixin, DetailView):
    model = App
    pk_url_kwarg = 'app_id'
    context_object_name = 'app'
    template_name = 'maker/app/index.html'

    def get_repo(self):
        return self.get_object().repo

    def get_context_data(self, **kwargs):
        context = super(AppDetailView, self).get_context_data(**kwargs)
        app = context['app']
        if app.name is None or app.name == '':
            raise RuntimeError("App has not been created properly.")
        context['apks'] = ApkPointer.objects.filter(app=app).order_by('-apk__version_code')
        if context['apks']:
            context['latest_apk'] = context['apks'][0].apk
        return context


class AppForm(BaseModelForm):
    screenshots = FileField(required=False, widget=ClearableFileInput(attrs={'multiple': True}))
    apks = FileField(required=False, widget=ClearableFileInput(attrs={'multiple': True}))

    def __init__(self, *args, **kwargs):
        super(AppForm, self).__init__(*args, **kwargs)
        if self.instance.category:
            # Show only own and default categories
            self.fields['category'].queryset = Category.objects.filter(
                Q(user=None) | Q(user=self.instance.repo.user))

    class Meta:
        model = App
        fields = ['summary', 'description', 'author_name', 'website', 'category', 'screenshots',
                  'apks']
# TODO #31
#        widgets = {'description': TinyMCE()}


class AppUpdateView(RepositoryAuthorizationMixin, UpdateView):
    model = App
    form_class = AppForm
    pk_url_kwarg = 'app_id'
    template_name = 'maker/app/edit.html'

    def get_repo(self):
        return self.get_object().repo

    def get_context_data(self, **kwargs):
        context = super(AppUpdateView, self).get_context_data(**kwargs)
        context['apks'] = ApkPointer.objects.filter(app=self.object).order_by('-apk__version_code')
        return context

    def form_valid(self, form):
        result = super(AppUpdateView, self).form_valid(form)

        for screenshot in self.request.FILES.getlist('screenshots'):
            Screenshot.objects.create(app=self.object, file=screenshot)

        for apk in self.request.FILES.getlist('apks'):
            pointer = ApkPointer.objects.create(repo=self.object.repo, file=apk)
            try:
                # TODO check that the APK belongs to this app and that signature matches
                pointer.initialize()  # this also attaches the app
            except Exception as e:
                pointer.delete()
                raise e

        form.instance.repo.update_async()  # schedule repository update
        return result


class AppDeleteView(RepositoryAuthorizationMixin, DeleteView):
    model = App
    pk_url_kwarg = 'app_id'
    template_name = 'maker/app/delete.html'

    def get_repo(self):
        return self.get_object().repo

    def get_success_url(self):
        return reverse_lazy('repo', kwargs={'repo_id': self.kwargs['repo_id']})


class AppTranslationUpdateView(RepositoryAuthorizationMixin, UpdateView):
    model = App
    form_class = translationformset_factory(App, fields=['l_summary', 'l_description',
                                                         'feature_graphic'],
                                            widgets={'l_description': TinyMCE()}, extra=1)
    pk_url_kwarg = 'app_id'
    context_object_name = 'app'
    template_name = "maker/app/translate.html"

    def get_success_url(self):
        self.get_repo().update_async()  # schedule repository update
        return reverse('app', kwargs=self.kwargs)
