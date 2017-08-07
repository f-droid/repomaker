import json
import logging
import time

import repomaker.models
from background_task import background
from background_task.signals import task_failed
from background_task.tasks import DBTaskRunner
from django.core.exceptions import ObjectDoesNotExist
from django.db.utils import OperationalError
from django.dispatch import receiver
from django.utils import timezone

PRIORITY_REPO = -1
PRIORITY_REMOTE_REPO = -2
PRIORITY_REMOTE_APP_ICON = -3


@background(schedule=timezone.now())
def update_repo(repo_id):
    try:
        repo = repomaker.models.Repository.objects.get(pk=repo_id)
    except ObjectDoesNotExist as e:
        logging.warning('Repository does not exist anymore, dropping task. (%s)', e)
        return

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


@background(schedule=timezone.now())
def update_remote_repo(remote_repo_id):
    try:
        remote_repo = repomaker.models.RemoteRepository.objects.get(pk=remote_repo_id)
    except ObjectDoesNotExist as e:
        logging.warning('Remote Repository does not exist anymore, dropping task. (%s)', e)
        # TODO cancel repeating task
        return

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
def update_remote_app_icon(remote_app_id, icon_name):
    try:
        remote_app = repomaker.models.RemoteApp.objects.get(pk=remote_app_id)
    except ObjectDoesNotExist as e:
        logging.warning('Remote App does not exist anymore, dropping task. (%s)', e)
        return
    remote_app.update_icon(icon_name)


@background(schedule=timezone.now())
def download_apk(apk_id, url):
    try:
        apk = repomaker.models.Apk.objects.get(pk=apk_id)
    except ObjectDoesNotExist as e:
        logging.warning('APK does not exist anymore, dropping task. (%s)', e)
        return

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
    try:
        app = repomaker.models.App.objects.get(pk=app_id)
    except ObjectDoesNotExist as e:
        logging.warning('App does not exist anymore, dropping task. (%s)', e)
        return
    try:
        remote_app = repomaker.models.RemoteApp.objects.get(pk=remote_app_id)
    except ObjectDoesNotExist as e:
        logging.warning('Remote App does not exist anymore, dropping task. (%s)', e)
        return
    app.download_graphic_assets_from_remote_app(remote_app)


@background(schedule=timezone.now())
def download_remote_screenshot(screenshot_id, app_id):
    try:
        screenshot = repomaker.models.RemoteScreenshot.objects.get(pk=screenshot_id)
        screenshot.download(app_id)
    except ObjectDoesNotExist as e:
        logging.warning('Remote Screenshot does not exist anymore, dropping task. (%s)', e)


@receiver(task_failed)
def task_failed_receiver(**kwargs):
    task = kwargs['completed_task']

    if task.task_name == 'repomaker.tasks.update_remote_repo':
        # extract task parameters
        task_params = json.loads(task.task_params)
        params = task_params[0]
        remote_repo_id = params[0]

        # fetch and disable remote repository
        remote_repo = repomaker.models.RemoteRepository.objects.get(pk=remote_repo_id)
        remote_repo.disabled = True
        remote_repo.save()


class DesktopRunner(DBTaskRunner):

    def run_task(self, tasks, task):
        try:
            super().run_task.__wrapped__(self, tasks, task)
        except OperationalError as e:
            if str(e) == 'database is locked':
                time.sleep(0.25)
                return self.run_task(tasks, task)
            raise e

    def run_next_task(self, tasks, queue=None):
        try:
            return super().run_next_task.__wrapped__(self, tasks, queue)
        except OperationalError as e:
            if str(e) == 'database is locked':
                time.sleep(0.25)
                return self.run_next_task(tasks, queue=queue)
            raise e
