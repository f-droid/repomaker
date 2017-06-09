from django.forms import ModelForm
from django.http import HttpResponseNotFound
from django.urls import reverse_lazy
from django.utils.translation import ugettext_lazy as _
from django.views.generic.edit import CreateView, DeleteView

from maker.models import Apk, ApkPointer
from .repository import RepositoryAuthorizationMixin


class ApkForm(ModelForm):
    class Meta:
        model = Apk
        # TODO allow multiple files to be uploaded at once
        fields = ['file']
        labels = {
            'file': _('Select APK file for upload'),
        }

    class Media:
        js = ('maker/js/drag-and-drop.js',)


class ApkUploadView(RepositoryAuthorizationMixin, CreateView):
    model = ApkPointer
    form_class = ApkForm

    def get(self, request, *args, **kwargs):
        # don't answer GET requests
        return HttpResponseNotFound()

    def form_valid(self, form):
        # TODO handle multiple files to be uploaded here
        repo = self.get_repo()
        apk = form.save()  # needed to save file to disk for scanning
        try:
            apk.initialize(repo)
        except Exception as e:
            if apk.pk:
                apk.delete()
            raise e
        return super(ApkUploadView, self).form_valid(form)

    def get_success_url(self):
        self.get_repo().update_async()
        return reverse_lazy('repo', args=[self.get_repo().pk])


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
