from django.db.models import Q
from django.forms import FileField, ClearableFileInput
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, ListView
from django.views.generic.edit import UpdateView, DeleteView
from hvad.forms import translationformset_factory
from tinymce.widgets import TinyMCE

from maker.models import RemoteRepository, App, RemoteApp, ApkPointer, Screenshot
from maker.models.category import Category
from . import BaseModelForm
from .repository import RepositoryAuthorizationMixin


class MDLTinyMCE(TinyMCE):
    """
    Ugly hack to work around a conflict between MDL and TinyMCE. See #31 for more details.
    """
    def _media(self):
        media = super()._media()
        media._js.remove('django_tinymce/init_tinymce.js')  # pylint: disable=protected-access
        media._js.append('maker/js/mdl-tinymce.js')  # pylint: disable=protected-access
        return media
    media = property(_media)


class AppAddView(RepositoryAuthorizationMixin, ListView):
    model = RemoteApp
    context_object_name = 'apps'
    template_name = "maker/app/add.html"

    def post(self, request, *args, **kwargs):
        return self.get(self, request, *args, **kwargs)

    def get_queryset(self):
        qs = RemoteApp.objects.filter(repo__users__id=self.request.user.id)
        if 'remote_repo_id' in self.kwargs:
            qs = qs.filter(repo__pk=self.kwargs['remote_repo_id'])
        if 'search' in self.request.POST:
            query = self.request.POST['search']
            qs = qs.filter(Q(name__icontains=query) | Q(summary__icontains=query))
        if 'category_id' in self.kwargs:
            qs = qs.filter(category__id=self.kwargs['category_id'])
        return qs

    def get_context_data(self, **kwargs):
        context = super(AppAddView, self).get_context_data(**kwargs)
        context['repo'] = self.get_repo()
        context['remote_repos'] = RemoteRepository.objects.filter(users__id=self.request.user.id)
        context['categories'] = Category.objects.filter(
            Q(user=None) | Q(user=self.request.user))
        if 'remote_repo_id' in self.kwargs:
            context['remote_repo'] = RemoteRepository.objects.get(pk=self.kwargs['remote_repo_id'])
        if 'category_id' in self.kwargs:
            context['category'] = context['categories'].get(pk=self.kwargs['category_id'])
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
        widgets = {'description': MDLTinyMCE()}


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
                                            widgets={'l_description': MDLTinyMCE()}, extra=1)
    pk_url_kwarg = 'app_id'
    context_object_name = 'app'
    template_name = "maker/app/translate.html"

    def get_success_url(self):
        self.get_repo().update_async()  # schedule repository update
        return reverse('app', kwargs=self.kwargs)
