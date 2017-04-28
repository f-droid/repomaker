from django.contrib import admin
from hvad.admin import TranslatableAdmin

from .models import RemoteRepository, Repository, App, RemoteApp, Apk, ApkPointer, \
    RemoteApkPointer, Category, Screenshot, RemoteScreenshot
from .models.storage import StorageManager

admin.site.register(RemoteRepository)
admin.site.register(Repository)
admin.site.register(App, TranslatableAdmin)  # FIXME hides untranslated apps
admin.site.register(RemoteApp, TranslatableAdmin)  # FIXME hides untranslated remote apps
admin.site.register(Apk)
admin.site.register(ApkPointer)
admin.site.register(RemoteApkPointer)
admin.site.register(Category)
admin.site.register(Screenshot)
admin.site.register(RemoteScreenshot)

for storage in StorageManager.storage_models:
    admin.site.register(storage)
