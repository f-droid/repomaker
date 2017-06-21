from django.core.exceptions import ValidationError
from django.forms import FileField, ClearableFileInput
from django.http import HttpResponseNotFound
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView, DeleteView

from maker.models import Apk, ApkPointer
from . import BaseModelForm
from .repository import RepositoryAuthorizationMixin


class ApkForm(BaseModelForm):
    apks = FileField(required=False, widget=ClearableFileInput(attrs={'multiple': True}))

    class Meta:
        model = Apk
        fields = ['apks']

    class Media:
        js = ('maker/js/drag-and-drop.js',)


class ApkUploadView(RepositoryAuthorizationMixin, CreateView):
    model = ApkPointer
    form_class = ApkForm
    template_name = "maker/error.html"

    def get(self, request, *args, **kwargs):
        # don't answer GET requests
        return HttpResponseNotFound()

    def form_valid(self, form):
        result = super(ApkUploadView, self).form_valid(form)

        try:
            self.add_apks()
        except ValidationError as e:
            form.add_error('apks', e)
            return super(ApkUploadView, self).form_invalid(form)

        self.get_repo().update_async()  # schedule repository update
        return result

    def get_success_url(self):
        self.get_repo().update_async()
        return reverse_lazy('repo', args=[self.get_repo().pk])

    def add_apks(self):
        """
        :raise IntegrityError: APK is already added
        :raise ValidationError: APK file is invalid
        """
        repo = self.get_repo()
        for apk_file in self.request.FILES.getlist('apks'):
            apk = Apk.objects.create(file=apk_file)
            try:
                # TODO could this be part of an ApkUploadMixin that also extends RepositoryView?
                apk.initialize(repo)  # this also creates a pointer and attaches the app
            except Exception as e:
                if apk.pk:
                    apk.delete()
                raise e


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
