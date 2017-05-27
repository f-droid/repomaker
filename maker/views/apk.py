from django.urls import reverse_lazy
from django.views.generic.edit import DeleteView

from maker.models import ApkPointer
from .repository import RepositoryAuthorizationMixin


class ApkPointerDeleteView(RepositoryAuthorizationMixin, DeleteView):
    model = ApkPointer
    template_name = 'maker/app/apk_delete.html'
    pk_url_kwarg = 'pk'

    def get_repo(self):
        return self.get_object().app.repo

    def get_success_url(self):
        self.get_repo().update_async()
        return reverse_lazy('edit_app', kwargs={'repo_id': self.kwargs['repo_id'],
                                                'app_id': self.kwargs['app_id']})
