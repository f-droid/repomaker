from django.forms import BooleanField
from django.urls import reverse_lazy
from django.utils.translation import ugettext_lazy as _
from django.views.generic import DetailView, TemplateView
from django.views.generic.edit import CreateView, UpdateView, DeleteView, FormMixin

from repomaker.models.storage import StorageManager
from . import BaseModelForm
from .repository import RepositoryAuthorizationMixin


class StorageForm(BaseModelForm):
    main = BooleanField(required=False, initial=False, label=_('Primary Storage'),
                        help_text=_('Make this storage the primary storage of the repository.'))

    def get_initial_for_field(self, field, field_name):
        if field_name == 'main' and hasattr(self.instance, 'repo'):
            # main field is checked if repo has no URL or it is already the same as this storage
            return (not self.instance.repo.url) or \
                   self.instance.get_repo_url() == self.instance.repo.url
        return super().get_initial_for_field(field, field_name)

    class Meta:
        fields = ['main']


class MainStorageMixin(FormMixin):

    def __init__(self):
        pass

    def form_valid(self, form):
        # set repo URL to storage URL, if necessary or desired
        if 'main' not in form.cleaned_data or form.cleaned_data['main']:
            form.instance.repo.set_url(form.instance.get_repo_url())
        return super(MainStorageMixin, self).form_valid(form)


class StorageAddView(RepositoryAuthorizationMixin, TemplateView):
    template_name = 'repomaker/storage/index.html'

    def get_context_data(self, **kwargs):
        context = super(StorageAddView, self).get_context_data(**kwargs)
        context['repo'] = self.get_repo()
        return context


class StorageCreateView(RepositoryAuthorizationMixin, MainStorageMixin, CreateView):
    template_name = 'repomaker/storage/form.html'

    def get_context_data(self, **kwargs):
        context = super(StorageCreateView, self).get_context_data(**kwargs)
        context['repo'] = self.get_repo()
        context['storage_name'] = self.model.get_name()
        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if not self.get_repo().url:
            # remove main field, if this new storage must be the main one
            del form.fields['main']
        return form

    def form_valid(self, form):
        form.instance.repo = self.get_repo()
        return super(StorageCreateView, self).form_valid(form)

    def get_success_url(self):
        self.get_repo().update_async()
        return super(StorageCreateView, self).get_success_url()


class StorageDetailView(RepositoryAuthorizationMixin, DetailView):
    context_object_name = 'storage'

    def post(self, request, *args, **kwargs):
        # enable/disable storage
        storage = self.get_object()
        storage.disabled = request.POST['disabled'] == 'true'
        storage.save()
        if not storage.disabled:
            self.get_repo().update_async()
        return super(StorageDetailView, self).get(request, args, kwargs)


class StorageUpdateView(RepositoryAuthorizationMixin, MainStorageMixin, UpdateView):
    template_name = 'repomaker/storage/form.html'

    def get_context_data(self, **kwargs):
        context = super(StorageUpdateView, self).get_context_data(**kwargs)
        context['repo'] = self.get_repo()
        context['storage_name'] = self.model.get_name()
        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if form.instance.get_repo_url() == form.instance.repo.url:
            # disable main field if this storage is already the main one
            form.fields['main'].disabled = True
        return form

    def get_success_url(self):
        self.get_repo().update_async()
        return super(StorageUpdateView, self).get_success_url()


class StorageDeleteView(RepositoryAuthorizationMixin, DeleteView):
    template_name = 'repomaker/storage/delete.html'

    def delete(self, request, *args, **kwargs):
        storage = self.get_object()
        # if this was the main storage, unset the repo URL or promote a different storage
        storage_url = storage.get_repo_url()
        if storage_url == storage.repo.url:
            for s in StorageManager.get_storage(storage.repo):
                # fallback to this storage if it isn't the same
                if s.get_repo_url() != storage_url:
                    storage.repo.set_url(s.get_repo_url())
                    storage.repo.update_async()
                    return super().delete(request, *args, **kwargs)
            # we did not find another storage to use, so unset the main repo URL
            storage.repo.set_url(None)
        return super().delete(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy('repo', kwargs={'repo_id': self.kwargs['repo_id']})
