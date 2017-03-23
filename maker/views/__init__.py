from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden, \
    HttpResponseServerError
from django.shortcuts import render, get_object_or_404
from django.urls import reverse

from maker.models import Repository, SshStorage, S3Storage, App, Apk
from maker.models.apk import ApkForm
from maker.models.app import AppForm
from maker.models.repository import RepositoryForm


def index(request):
    if request.user.is_authenticated:
        repositories = Repository.objects.filter(user=request.user)
        context = {'repositories': repositories}
        return render(request, 'maker/index.html', context)
    else:
        return HttpResponseRedirect('/admin/login/')


def add_repo(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/admin/login/')
    if request.method == 'POST':
        form = RepositoryForm(request.POST, request.FILES)
        if form.is_valid():
            # get and save repo
            repo = form.save(commit=False)
            repo.user = request.user
            repo.save()
            form.save_m2m()

            # generate repo, QR Code, etc. on disk
            repo.create()

            return HttpResponseRedirect(reverse('repo', args=[repo.id]))
        else:
            return HttpResponseServerError("Invalid Form: " + str(form.errors))
    else:
        form = RepositoryForm()
        return render(request, 'maker/repo/add.html', {'form': form})


def show_repo(request, repo_id):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/admin/login/')

    repo = get_object_or_404(Repository, pk=repo_id)
    if repo.user != request.user:
        return HttpResponseForbidden()

    ssh_storage = SshStorage.objects.filter(repo=repo)
    s3_storage = S3Storage.objects.filter(repo=repo)
    apps = App.objects.filter(repo=repo)
    context = {'repo': repo, 'ssh_storage': ssh_storage, 's3_storage': s3_storage, 'apps': apps}
    return render(request, 'maker/repo/index.html', context)


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
