from datetime import datetime, timezone

from django.test import TestCase

from maker.models import RemoteRepository, RemoteApp


class RemoteAppTestCase(TestCase):

    def setUp(self):
        date = datetime.fromtimestamp(0, timezone.utc)
        self.repo = RemoteRepository.objects.create(name="Test", last_change_date=date)
        self.app = RemoteApp.objects.create(repo=self.repo, package_id="org.example",
                                            last_updated_date=date)

    def test_update_translations_new(self):
        # update remote app translation with a new one
        localized = {'en': {'Summary': 'foo', 'Description': 'bar', 'video': 'bla'}}
        self.app._update_translations(localized)  # pylint: disable=protected-access

        # assert that translation has been saved
        app = RemoteApp.objects.language('en').get(pk=self.app.pk)
        self.assertEqual(localized['en']['Summary'], app.l_summary)
        self.assertEqual(localized['en']['Description'], app.l_description)

    def test_update_translations_existing(self):
        # add a new translation
        self.test_update_translations_new()
        self.assertTrue(RemoteApp.objects.language('en').exists())

        # update existing translation
        localized = {'en': {'Summary': 'newfoo', 'Description': 'newbar', 'video': 'bla'}}
        self.app._update_translations(localized)  # pylint: disable=protected-access

        # assert that translation has been updated
        app = RemoteApp.objects.language('en').get(pk=self.app.pk)
        self.assertEqual(localized['en']['Summary'], app.l_summary)
        self.assertEqual(localized['en']['Description'], app.l_description)

    def test_apply_translation(self):
        # apply new translation
        translation = {'Summary': 'test1', 'Description': 'test2'}
        self.app.translate('en')
        self.app.apply_translation(translation)

        # assert that translation has been saved
        app = RemoteApp.objects.language('en').get(pk=self.app.pk)
        self.assertEqual(translation['Summary'], app.l_summary)
        self.assertEqual(translation['Description'], app.l_description)
