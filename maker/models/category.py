from django.contrib.auth.models import User
from django.db import models


class Category(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    name = models.CharField(max_length=64)

    def __str__(self):
        return str(self.name)

    class Meta:
        verbose_name_plural = "Categories"
        unique_together = (("user", "name"),)
