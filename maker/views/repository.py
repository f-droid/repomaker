from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _
from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView

from maker.models import Repository, App
from maker.models.storage import StorageManager
from . import BaseModelForm, LoginOrSingleUserRequiredMixin


# noinspection PyUnresolvedReferences
class RepositoryAuthorizationMixin(LoginOrSingleUserRequiredMixin, UserPassesTestMixin):
    """
    Mixin that checks if the current users is authorized to view this repository.
    It raises a PermissionDenied exception if the user is not authorized.
    """
    raise_exception = True

    def get_repo(self):
        return get_object_or_404(Repository, pk=self.kwargs['repo_id'])

    def test_func(self):
        return self.get_repo().user == self.request.user


class RepositoryListView(LoginOrSingleUserRequiredMixin, ListView):
    model = Repository
    context_object_name = 'repositories'
    template_name = "maker/index.html"

    def get_queryset(self):
        return Repository.objects.filter(user=self.request.user)


class RepositoryForm(BaseModelForm):
    class Meta:
        model = Repository
        fields = ['name', 'description', 'url', 'icon']
        labels = {
            'url': _('Main URL'),
            'icon': _('Upload Repository Icon'),
        }
        help_texts = {
            'url': _('This is the primary location where your repository will be made available.'),
        }


class RepositoryCreateView(LoginOrSingleUserRequiredMixin, CreateView):
    model = Repository
    form_class = RepositoryForm
    template_name = "maker/repo/add.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        result = super(RepositoryCreateView, self).form_valid(form)
        # TODO show loading screen
        form.instance.create()  # generate repo, QR Code, etc. on disk
        return result


class RepositoryDetailView(RepositoryAuthorizationMixin, DetailView):
    model = Repository
    pk_url_kwarg = 'repo_id'
    context_object_name = 'repo'
    template_name = 'maker/repo/index.html'

    def get_repo(self):
        return self.get_object()

    def get_context_data(self, **kwargs):
        context = super(RepositoryDetailView, self).get_context_data(**kwargs)
        repo = context['repo']
        if repo.fingerprint is None or repo.fingerprint == '':
            raise RuntimeError("Repository has not been created properly.")

        context['storage'] = StorageManager.get_storage(repo)
        context['apps'] = App.objects.filter(repo=repo)
        return context
