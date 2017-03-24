from django.urls import reverse_lazy
from django.views.generic.edit import CreateView, UpdateView, DeleteView

from .repository import RepositoryAuthorizationMixin


class StorageCreateView(RepositoryAuthorizationMixin, CreateView):

    def form_valid(self, form):
        form.instance.repo = self.get_repo()
        return super(StorageCreateView, self).form_valid(form)

    def get_success_url(self):
        return get_success_url(self)


class StorageUpdateView(RepositoryAuthorizationMixin, UpdateView):

    def get_success_url(self):
        return get_success_url(self)


class StorageDeleteView(RepositoryAuthorizationMixin, DeleteView):

    def get_success_url(self):
        return get_success_url(self)


def get_success_url(view):
    return reverse_lazy('repo', kwargs={'repo_id': view.kwargs['repo_id']})
