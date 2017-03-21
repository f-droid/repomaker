from django.contrib import admin

from .models import Repository, S3Storage, App, Apk

admin.site.register(Repository)
admin.site.register(S3Storage)
admin.site.register(App)
admin.site.register(Apk)
