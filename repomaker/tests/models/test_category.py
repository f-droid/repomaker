from django.test import TestCase

from repomaker.migrations.default_categories import DEFAULT_CATEGORIES
from repomaker.models import Category


class CategoryTestCase(TestCase):

    def test_pre_install(self):
        categories = Category.objects.all()
        self.assertEqual(len(DEFAULT_CATEGORIES), len(categories))
        for c in categories:
            self.assertTrue(c.name in DEFAULT_CATEGORIES)

    def test_str(self):
        category = Category.objects.get(name=DEFAULT_CATEGORIES[0])
        self.assertEqual(category.name, str(category))
