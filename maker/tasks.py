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

    repo.update()
    # TODO always publish after each update
#    repo.publish()

    repo.is_updating = False
    repo.save()
