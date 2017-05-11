from background_task import background
from django.utils import timezone

import maker.models


@background(schedule=timezone.now())
def update_repo(repo_id):
    repo = maker.models.repository.Repository.objects.get(pk=repo_id)
    if repo.is_updating:
        return  # don't update the same repo concurrently
    repo.update_scheduled = False
    repo.is_updating = True
    repo.save()

    try:
        repo.update()
        repo.publish()
    finally:
        repo.is_updating = False
        repo.save()


# TODO update remote repositories periodically
# http://django-background-tasks.readthedocs.io/en/latest/#repeating-tasks
@background(schedule=timezone.now())
def update_remote_repo(remote_repo_id):
    remote_repo = maker.models.repository.RemoteRepository.objects.get(pk=remote_repo_id)
    if remote_repo.is_updating:
        return  # don't update the same repo concurrently
    remote_repo.update_scheduled = False
    remote_repo.is_updating = True
    remote_repo.save()

    try:
        remote_repo.update_index()
    finally:
        remote_repo.is_updating = False
        remote_repo.save()


@background(schedule=timezone.now())
def download_apk(apk_id, url):
    apk = maker.models.apk.Apk.objects.get(pk=apk_id)
    if apk.is_downloading:
        return  # don't download the same apk concurrently
    apk.is_downloading = True
    apk.save()

    try:
        apk.download(url)
    finally:
        apk.is_downloading = False
        apk.save()


@background(schedule=timezone.now())
def download_remote_graphic_assets(app_id, remote_app_id):
    app = maker.models.app.App.objects.get(pk=app_id)
    remote_app = maker.models.app.RemoteApp.objects.get(pk=remote_app_id)
    app.download_graphic_assets_from_remote_app(remote_app)


@background(schedule=timezone.now())
def download_remote_screenshot(screenshot_id, app_id):
    screenshot = maker.models.screenshot.RemoteScreenshot.objects.get(pk=screenshot_id)
    screenshot.download(app_id)
