from django.contrib import admin
from hvad.admin import TranslatableAdmin

from .models import Repository, RemoteRepository, App, RemoteApp, Apk, ApkPointer, \
    RemoteApkPointer, Category, Screenshot, RemoteScreenshot
from .models.storage import StorageManager

admin.site.register(Repository)
admin.site.register(RemoteRepository)
admin.site.register(App, TranslatableAdmin)  # hides untranslated apps which should not exist
admin.site.register(RemoteApp, TranslatableAdmin)  # hides untranslated apps which should not exist
admin.site.register(Apk)
admin.site.register(ApkPointer)
admin.site.register(RemoteApkPointer)
admin.site.register(Category)
admin.site.register(Screenshot)
admin.site.register(RemoteScreenshot)

for storage in StorageManager.storage_models:
    admin.site.register(storage)
