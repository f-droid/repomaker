import logging

from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.utils import OperationalError, IntegrityError
from django.forms import Textarea
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _
from django.views.generic import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView

from maker.models import Repository, App, Apk
from maker.models.storage import StorageManager
from . import BaseModelForm, LoginOrSingleUserRequiredMixin


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
        fields = ['name', 'description']
        labels = {
            'description': _('Describe the repo'),
        }
        widgets = {
            'description': Textarea(attrs={
                'rows': 2,
            }),
        }


class RepositoryCreateView(LoginOrSingleUserRequiredMixin, CreateView):
    model = Repository
    form_class = RepositoryForm
    template_name = "maker/repo/add.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        result = super(RepositoryCreateView, self).form_valid(form)  # saves new repo

        # set main repo URL to that of first default storage, if any exists
        storage = StorageManager.get_default_storage(form.instance)
        if len(storage) > 0:
            form.instance.url = storage[0].get_repo_url()

        # TODO show loading screen

        form.instance.create()  # generate repo, QR Code, etc. on disk
        return result


class RepositoryView(RepositoryAuthorizationMixin, ListView):
    model = App
    paginate_by = 15
    context_object_name = 'apps'
    template_name = 'maker/repo/index.html'

    def get_queryset(self):
        qs = App.objects.filter(repo=self.get_repo())
        if 'search' in self.request.GET:
            query = self.request.GET['search']
            # TODO do a better weighted search query that takes description into account
            qs = qs.filter(Q(name__icontains=query) | Q(summary__icontains=query))
        return qs

    def get_context_data(self, **kwargs):
        context = super(RepositoryView, self).get_context_data(**kwargs)
        repo = self.get_repo()
        context['repo'] = repo
        if repo.fingerprint is None or repo.fingerprint == '':
            raise RuntimeError("Repository has not been created properly.")

        context['storage'] = StorageManager.get_storage(repo)
        from .apk import ApkForm
        context['form'] = ApkForm()
        if 'search' in self.request.GET and self.request.GET['search'] != '':
            context['search_params'] = 'search=%s' % self.request.GET['search']
        return context

    def post(self, request, *args, **kwargs):
        if 'HTTP_RM_BACKGROUND_TYPE' in request.META:
            if request.META['HTTP_RM_BACKGROUND_TYPE'] == 'apks':
                try:
                    self.add_apks()
                except OperationalError as e:
                    logging.error(e)
                    return HttpResponse(e, status=500)
                except IntegrityError as e:
                    logging.error(e)
                    return HttpResponse(e.message, status=400)
                except ValidationError as e:
                    logging.error(e)
                    return HttpResponse(e.message, status=400)
                self.get_repo().update_async()  # schedule repository update
                return HttpResponse(status=204)
        return Http404()

    def add_apks(self):
        """
        :raise IntegrityError: APK is already added
        :raise ValidationError: APK file is invalid
        """
        repo = self.get_repo()
        for apk_file in self.request.FILES.getlist('apks'):
            apk = Apk.objects.create(file=apk_file)
            try:
                apk.initialize(repo)  # this also creates a pointer and attaches the app
            except Exception as e:
                if apk.pk:
                    apk.delete()
                raise e


class RepositoryUpdateView(RepositoryAuthorizationMixin, UpdateView):
    model = Repository
    form_class = RepositoryForm
    pk_url_kwarg = 'repo_id'
    context_object_name = 'repo'
    template_name = 'maker/repo/edit.html'

    def form_valid(self, form):
        result = super(RepositoryUpdateView, self).form_valid(form)
        form.instance.update_async()  # schedule repository update
        return result


class RepositoryDeleteView(RepositoryAuthorizationMixin, DeleteView):
    model = Repository
    pk_url_kwarg = 'repo_id'
    template_name = 'maker/repo/delete.html'

    def get_success_url(self):
        return '/'
