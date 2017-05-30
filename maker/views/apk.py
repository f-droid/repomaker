from django.forms import ModelForm
from django.http import HttpResponseNotFound, HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import ugettext_lazy as _
from django.views.generic.edit import CreateView, DeleteView

from maker.models import ApkPointer
from .repository import RepositoryAuthorizationMixin


class ApkForm(ModelForm):
    class Meta:
        model = ApkPointer
        # TODO allow multiple files to be uploaded at once
        fields = ['file']
        labels = {
            'file': _('Select APK file for upload'),
        }


class ApkUploadView(RepositoryAuthorizationMixin, CreateView):
    model = ApkPointer
    form_class = ApkForm

    def get(self, request, *args, **kwargs):
        # don't answer GET requests
        return HttpResponseNotFound()

    def form_valid(self, form):
        form.instance.repo = self.get_repo()
        # TODO handle multiple files to be uploaded here
        pointer = form.save()  # needed to save file to disk for scanning
        try:
            pointer.initialize()
        except Exception as e:
            pointer.delete()
            raise e

        args = [pointer.repo.pk, pointer.app.pk]
        if pointer.app.summary != '':  # app did exist already, show it
            return HttpResponseRedirect(reverse('app', args=args))
        return HttpResponseRedirect(reverse('edit_app', args=args))


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
