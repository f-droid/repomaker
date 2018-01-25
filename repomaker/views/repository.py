import collections
import logging

from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Q
from django.forms import Textarea
from django.http import HttpResponseServerError, HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _
from django.views.generic import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView

from repomaker.models import Repository, App, Apk
from repomaker.models.storage import StorageManager
from . import BaseModelForm, AppScrollListView, LoginOrSingleUserRequiredMixin, ErrorView


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


class ApkUploadMixin(RepositoryAuthorizationMixin):
    apks_added = False

    def post(self, request, *args, **kwargs):
        if not self.apks_added and 'apks' in self.request.FILES:
            added_apks = self.add_apks()
            if len(added_apks['failed']) > 0:
                # TODO return list, so JavaScript can handle the individual error properly
                return HttpResponseServerError(self.get_error_msg(added_apks['failed']))
            return HttpResponse(status=204)
        # noinspection PyUnresolvedReferences
        return super().post(request, args, kwargs)

    def add_apks(self, app=None):
        """
        Adds uploaded APKs from the request object to the database and initializes them

        :return: A dict with the successfully initialized APKs in a list called 'apks' and a list of
                 tuples called 'failed', one tuple for each failed APK file where the first element
                 is the name of the APK file and the second an error message
        """
        files = self.request.FILES.getlist('apks')
        repo = self.get_repo()

        apks = []
        failed = []
        for apk_file in files:
            apk = Apk.objects.create(file=apk_file)
            try:
                apk = apk.initialize(repo, app)  # this also creates a pointer and attaches the app
                apks.append(apk)
            except Exception as e:
                logging.warning(e)
                if apk.pk:
                    apk.delete()
                if isinstance(e, collections.Iterable):
                    tup = (apk_file, ' '.join(e))
                else:
                    tup = (apk_file, str(e))
                failed.append(tup)

        if len(files) > len(failed):
            self.get_repo().update_async()  # schedule repository update

        self.apks_added = True
        return {
            'apks': apks,
            'failed': failed,
        }

    @staticmethod
    def get_error_msg(failed):
        error_msg = ''
        for file, error in failed:
            error_msg += str(file) + ': ' + error + '\n'
        return error_msg


class RepositoryListView(LoginOrSingleUserRequiredMixin, ListView):
    model = Repository
    context_object_name = 'repositories'
    template_name = "repomaker/index.html"

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
    template_name = "repomaker/repo/add.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        result = super(RepositoryCreateView, self).form_valid(form)  # saves new repo

        try:
            # generate repo, QR Code, etc. on disk
            form.instance.create()

            # set main repo URL to that of first default storage, if any exists
            storage = StorageManager.get_default_storage(form.instance)
            if len(storage) > 0:
                # requires repo fingerprint to exist
                form.instance.set_url(storage[0].get_repo_url())  # saves form.instance
        except Exception as e:
            logging.error('Creating repo failed: %s', e)
            form.instance.delete()
            error = _('There was an error creating the repository. Please try again!')
            return ErrorView().dispatch(self.request, error=error + ' ' + str(e))
        return result


class RepositoryView(ApkUploadMixin, AppScrollListView):
    model = App
    context_object_name = 'apps'
    template_name = 'repomaker/repo/index.html'

    def get_queryset(self):
        qs = App.objects.language().fallbacks().filter(repo=self.get_repo()).order_by('added_date')
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
        if 'HTTP_RM_BACKGROUND_TYPE' in request.META and \
                        request.META['HTTP_RM_BACKGROUND_TYPE'] == 'apks':
            return super(RepositoryView, self).post(request, *args, **kwargs)
        return Http404()


class RepositoryUpdateView(RepositoryAuthorizationMixin, UpdateView):
    model = Repository
    form_class = RepositoryForm
    pk_url_kwarg = 'repo_id'
    context_object_name = 'repo'
    template_name = 'repomaker/repo/edit.html'

    def form_valid(self, form):
        result = super(RepositoryUpdateView, self).form_valid(form)
        form.instance.update_async()  # schedule repository update
        return result


class RepositoryDeleteView(RepositoryAuthorizationMixin, DeleteView):
    model = Repository
    pk_url_kwarg = 'repo_id'
    template_name = 'repomaker/repo/delete.html'

    def get_success_url(self):
        return '/'
