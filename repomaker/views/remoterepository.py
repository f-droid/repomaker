import json
import logging
import urllib.parse

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.utils import OperationalError
from django.http import HttpResponseRedirect, Http404, HttpResponse, HttpResponseServerError
from django.urls import reverse_lazy
from django.utils.translation import ugettext_lazy as _
from django.views.generic import DetailView
from django.views.generic.edit import CreateView
from fdroidserver import index

from repomaker.models import Repository, RemoteRepository, RemoteApp
from repomaker.models.category import Category
from repomaker.models.screenshot import PHONE, RemoteScreenshot
from . import BaseModelForm, AppScrollListView, LoginOrSingleUserRequiredMixin, LanguageMixin
from .repository import RepositoryAuthorizationMixin


class RemoteRepositoryForm(BaseModelForm):
    class Meta:
        model = RemoteRepository
        fields = ['url']
        labels = {
            'url': _('Repository URL'),
        }


class RemoteRepositoryCreateView(LoginOrSingleUserRequiredMixin, CreateView):
    model = RemoteRepository
    form_class = RemoteRepositoryForm
    template_name = "repomaker/repo/add.html"

    def form_valid(self, form):
        user = self.request.user

        # ensure that URL contains a fingerprint
        url = urllib.parse.urlsplit(form.instance.url)
        query = urllib.parse.parse_qs(url.query)
        if 'fingerprint' not in query:
            form.add_error('url', _("Please use a URL with a fingerprint at the end" +
                           ", so we can validate the authenticity of the repository."))
            return self.form_invalid(form)

        # check if the user is trying to add their own repo here
        fingerprint = query['fingerprint'][0]
        if Repository.objects.filter(user=user, fingerprint=fingerprint).exists():
            form.add_error('url', _("Please don't add one of your own repositories here."))
            return self.form_invalid(form)

        # update URL and fingerprint to final values
        new_url = urllib.parse.SplitResult(url.scheme, url.netloc, url.path, '', '')
        form.instance.url = new_url.geturl()
        form.instance.fingerprint = fingerprint

        # check if this remote repo already exists and if so, re-use it
        existing_repo_query = RemoteRepository.objects.filter(fingerprint=fingerprint)
        if existing_repo_query.exists():
            existing_repo = existing_repo_query.get()
            existing_repo.users.add(user)
            existing_repo.save()
            return HttpResponseRedirect(self.get_success_url())

        # download repo index and apply information to instance
        try:
            form.instance.update_index(update_apps=False)
            form.instance.update_async()  # schedule an async update for the apps as well
        except index.VerificationException as e:
            form.add_error('url', _("Could not validate repository: %s") % e)
            return self.form_invalid(form)

        result = super(RemoteRepositoryCreateView, self).form_valid(form)
        form.instance.users.add(user)
        form.instance.save()
        return result

    def get_success_url(self):
        # TODO point this to some sort of remote repo overview or detail view
        return reverse_lazy('index')


class AppRemoteAddView(RepositoryAuthorizationMixin, AppScrollListView):
    model = RemoteApp
    context_object_name = 'apps'
    template_name = "repomaker/repo/remotes.html"

    def get_queryset(self):
        qs = RemoteApp.objects.language().fallbacks().filter(repo__users__id=self.request.user.id) \
            .order_by('added_date')
        if 'remote_repo_id' in self.kwargs:
            qs = qs.filter(repo__pk=self.kwargs['remote_repo_id'])
        if 'search' in self.request.GET:
            query = self.request.GET['search']
            qs = qs.filter(Q(name__icontains=query) | Q(summary__icontains=query))
        if 'category_id' in self.kwargs:
            qs = qs.filter(category__id=self.kwargs['category_id'])
        return qs

    def get_context_data(self, **kwargs):
        context = super(AppRemoteAddView, self).get_context_data(**kwargs)
        context['repo'] = self.get_repo()
        context['remote_repos'] = RemoteRepository.objects.filter(users__id=self.request.user.id)
        context['categories'] = Category.objects.filter(Q(user=None) | Q(user=self.request.user))
        if 'remote_repo_id' in self.kwargs:
            context['remote_repo'] = RemoteRepository.objects.get(pk=self.kwargs['remote_repo_id'])
        if 'category_id' in self.kwargs:
            context['category'] = context['categories'].get(pk=self.kwargs['category_id'])
        if 'search' in self.request.GET and self.request.GET['search'] != '':
            context['search_params'] = 'search=%s' % self.request.GET['search']
        for app in context['apps']:
            app.added = app.is_in_repo(context['repo'])
        return context

    def post(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        if request.is_ajax():
            apps_to_add = json.loads(request.body.decode("utf-8"))
            for app in apps_to_add:
                app_id = app['appId']
                remote_repo_id = app['appRepoId']
                remote_app = RemoteApp.objects.language().fallbacks() \
                    .get(repo__id=remote_repo_id, pk=app_id, repo__users__id=request.user.id)
                try:
                    remote_app.add_to_repo(self.get_repo())
                except OperationalError as e:
                    logging.error(e)
                    return HttpResponseServerError(e)
                except ValidationError as e:
                    logging.error(e)
                    return HttpResponse(e.message, status=400)
            self.get_repo().update_async()  # schedule repository update
            return HttpResponse(status=204)
        return Http404()


class RemoteAppImportView(RepositoryAuthorizationMixin, LanguageMixin, DetailView):
    model = RemoteApp
    pk_url_kwarg = 'app_id'
    context_object_name = 'app'
    template_name = "repomaker/app/remote_add.html"

    def get_queryset(self):
        # restricting query set for security and to add language selector
        remote_repo_id = self.kwargs['remote_repo_id']
        qs = RemoteApp.objects.language(self.get_language())
        return qs.filter(repo__id=remote_repo_id, repo__users__id=self.request.user.id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['repo'] = self.get_repo()
        context['screenshots'] = RemoteScreenshot.objects.filter(app=self.get_object(), type=PHONE,
                                                                 language_code=self.get_language())
        return context

    def post(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        if not self.get_queryset().exists():
            return Http404()

        remote_app = self.get_object()
        # TODO catch ValidationError and display proper error message on a page
        app = remote_app.add_to_repo(self.get_repo())

        return HttpResponseRedirect(app.get_absolute_url())


class RemoteAppImportViewScreenshots(RemoteAppImportView):

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['show_screenshots'] = True
        return context
