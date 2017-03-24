from django.db.models import Q
from django.forms import ModelForm
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.urls import reverse_lazy
from django.views.generic import DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView

from maker.models import Repository, App, Apk
from maker.models.category import Category
from .repository import RepositoryAuthorizationMixin


class ApkForm(ModelForm):
    class Meta:
        model = Apk
        fields = ['file']


class AppCreateView(RepositoryAuthorizationMixin, CreateView):
    model = Apk
    form_class = ApkForm
    template_name = "maker/app/add.html"

    def form_valid(self, form):
        repo = self.get_repo()
        app = App(repo=repo)  # create temporary app for APK
        app.save()
        form.instance.app = app

        try:
            result = super(AppCreateView, self).form_valid(form)
            apk = self.object
            apk_result = apk.store_data_from_file()
            if apk_result is not None:
                apk.delete()
                app.delete()
                return apk_result
        except Exception as e:
            form.instance.delete()
            if app.id == form.instance.app.id:  # app did not exist already
                app.delete()
            raise e

        if app.id != apk.app.id:  # app did exist already, show it
            return HttpResponseRedirect(reverse('app', args=[repo.pk, apk.app.pk]))
        return result

    def get_success_url(self):
        # edit new app
        return reverse_lazy('edit_app', kwargs={'repo_id': self.object.app.repo.pk,
                                                'app_id': self.object.app.pk})


class AppDetailView(RepositoryAuthorizationMixin, DetailView):
    model = App
    pk_url_kwarg = 'app_id'
    context_object_name = 'app'
    template_name = 'maker/app/index.html'

    def get_repo(self):
        return self.get_object().repo

    def get_context_data(self, **kwargs):
        context = super(AppDetailView, self).get_context_data(**kwargs)
        app = context['app']
        if app.name is None or app.name == '':
            raise RuntimeError("App has not been created properly.")
        context['apks'] = Apk.objects.filter(app=app).order_by('-version_code')
        return context


class AppForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super(AppForm, self).__init__(*args, **kwargs)
        if self.instance.category:
            # Show only own and default categories
            self.fields['category'].queryset = Category.objects.filter(
                Q(user=None) | Q(user=self.instance.repo.user))

    class Meta:
        model = App
        fields = ['summary', 'description', 'website', 'category']


class AppUpdateView(RepositoryAuthorizationMixin, UpdateView):
    model = App
    form_class = AppForm
    pk_url_kwarg = 'app_id'
    template_name = 'maker/app/edit.html'

    def get_repo(self):
        return self.get_object().repo

    def form_valid(self, form):
        result = super(AppUpdateView, self).form_valid(form)
        form.instance.repo.update_async()  # schedule repository update
        return result


class AppDeleteView(RepositoryAuthorizationMixin, DeleteView):
    model = App
    pk_url_kwarg = 'app_id'
    template_name = 'maker/app/delete.html'

    def get_repo(self):
        return self.get_object().repo

    def get_success_url(self):
        return reverse_lazy('repo', kwargs={'repo_id': self.kwargs['repo_id']})
