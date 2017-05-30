import urllib.parse

from django.core.exceptions import ValidationError
from django.db.utils import OperationalError
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.translation import ugettext_lazy as _
from django.views.generic import View
from django.views.generic.edit import CreateView
from fdroidserver import index

from maker.models import RemoteRepository, Repository, RemoteApp
from maker.views.repository import RepositoryAuthorizationMixin
from . import BaseModelForm, LoginOrSingleUserRequiredMixin


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
    template_name = "maker/repo/add.html"

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


class RemoteAppCreateView(RepositoryAuthorizationMixin, CreateView):
    template_name = "maker/app/remote_add.html"
    fields = []
    object = None

    def get_queryset(self):
        remote_repo_id = self.kwargs['remote_repo_id']
        app_id = self.kwargs['app_id']
        return RemoteApp.objects.filter(repo__id=remote_repo_id,
                                        repo__users__id=self.request.user.id, pk=app_id)

    def get_context_data(self, **kwargs):
        context = super(RemoteAppCreateView, self).get_context_data(**kwargs)
        context['app'] = self.get_queryset().get()
        context['repo'] = self.get_repo()
        return context

    def form_valid(self, form):
        # ignore the form
        if not self.get_queryset().exists():
            return Http404()

        remote_app = self.get_queryset().get()
        # TODO catch ValidationError and display proper error message on a page
        self.object = remote_app.add_to_repo(self.get_repo())

        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        # edit new app
        return reverse_lazy('app', kwargs={'repo_id': self.object.repo.pk,
                                           'app_id': self.object.pk})


# TODO remove and use RemoteAppCreateView instead
# https://docs.djangoproject.com/en/1.11/topics/class-based-views/mixins/#more-than-just-html
class RemoteAppCreateHeadlessView(RepositoryAuthorizationMixin, View):
    def post(self, request, *args, **kwargs):
        remote_repo_id = kwargs['remote_repo_id']
        app_id = kwargs['app_id']
        remote_app = RemoteApp.objects.get(repo__id=remote_repo_id, pk=app_id,
                                           repo__users__id=request.user.id)
        try:
            remote_app.add_to_repo(self.get_repo())
        except ValidationError as e:
            # TODO: Identify error based on code
            if "This app does already exist in your repository." == e.message:
                return HttpResponse(1)
            return HttpResponse(False)
        except OperationalError:
            return HttpResponse(2)
        self.get_repo().update_async()  # schedule repository update
        return HttpResponse(True)
