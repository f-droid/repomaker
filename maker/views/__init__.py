from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden, \
    HttpResponseServerError
from django.shortcuts import render, get_object_or_404
from django.urls import reverse

from maker import DEFAULT_USER_NAME
from maker.models import Repository, App, Apk
from maker.models.apk import ApkForm
from maker.models.app import AppForm


def add_app(request, repo_id):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/admin/login/')

    repo = get_object_or_404(Repository, pk=repo_id)
    if repo.user != request.user:
        return HttpResponseForbidden()

    if request.method == 'POST':
        app = App(repo=repo)
        app.save()
        apk = Apk(app=app)
        form = ApkForm(request.POST, request.FILES, instance=apk)
        if not form.is_valid():
            app.delete()
            return HttpResponseServerError('Invalid APK')

        try:
            apk = form.save()
            result = apk.store_data_from_file()
            if result is not None:
                apk.delete()
                app.delete()
                return result
            repo.update_async()

            if app.id == apk.app.id:  # app did not exist already
                return HttpResponseRedirect(reverse('edit_app', args=[repo_id, apk.app.id]))
            else:
                return HttpResponseRedirect(reverse('app', args=[repo_id, apk.app.id]))
        except Exception as e:
            apk.delete()
            if app.id == apk.app.id:  # app did not exist already
                app.delete()
            raise e
    else:
        form = ApkForm()
    return render(request, 'maker/app/add.html', {'repo_id': repo_id, 'form': form})


def show_app(request, repo_id, app_id):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/admin/login/')

    app = get_object_or_404(App, pk=app_id)
    if app.repo.user != request.user:
        return HttpResponseForbidden()

    apks = Apk.objects.filter(app=app).order_by('-version_code')
    return render(request, 'maker/app/index.html',
                  {'repo_id': repo_id, 'app': app, 'apks': apks})


def edit_app(request, repo_id, app_id):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/admin/login/')

    app = get_object_or_404(App, pk=app_id)
    if app.repo.user != request.user:
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = AppForm(request.POST, instance=app)
        if form.is_valid():
            form.save()
            app.repo.update_async()
            return HttpResponseRedirect(reverse('app', args=[repo_id, app.id]))
        else:
            return HttpResponseServerError("Invalid Form")
    else:
        form = AppForm(instance=app)
        return render(request, 'maker/app/edit.html',
                      {'repo_id': repo_id, 'app': app, 'form': form})


def delete_app(request, repo_id, app_id):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/admin/login/')

    app = get_object_or_404(App, pk=app_id)
    if app.repo.user != request.user:
        return HttpResponseForbidden()

    app.delete()
    return HttpResponseRedirect(reverse('repo', args=[repo_id]))


def update(request, repo_id):
    repo = get_object_or_404(Repository, pk=repo_id)
    if repo.user != request.user:
        return HttpResponseForbidden()

    repo.update_async()
    return HttpResponse("Updated")


# TODO remove when automatic publishing has been activated
def publish(request, repo_id):
    repo = get_object_or_404(Repository, pk=repo_id)
    if repo.user != request.user:
        return HttpResponseForbidden()

    repo.publish()
    return HttpResponse("Published")


class LoginOrSingleUserRequiredMixin(LoginRequiredMixin):
    """
    Mixin that should be used for all class-based views within this project.
    It verifies that the current user is authenticated
    or logs in the default user in single-user mode.
    """

    def dispatch(self, request, *args, **kwargs):
        if settings.SINGLE_USER_MODE and not request.user.is_authenticated:
            user = User.objects.get(username=DEFAULT_USER_NAME)
            login(request, user)
        return super().dispatch(request, *args, **kwargs)
