from django.urls import reverse
from repomaker.models import App, Screenshot

from .. import RmTestCase


class ScreenshotViewTestCase(RmTestCase):

    def setUp(self):
        super().setUp()

        self.app = App.objects.create(
            repo=self.repo,
            package_id='org.example',
            name='AppName',
        )
        self.app.default_translate()
        self.app.save()

    def test_delete_screenshot(self):
        screenshot = Screenshot.objects.create(app=self.app, file='test.png')

        # request screenshot deletion confirmation page
        kwargs = {'repo_id': self.repo.id, 'app_id': self.app.id, 's_id': screenshot.id}
        response = self.client.get(reverse('screenshot_delete', kwargs=kwargs))

        # assert that it contains the relevant information
        self.assertContains(response, self.app.name)
        self.assertContains(response, screenshot.file.url)

        # request the screenshot to be deleted
        response = self.client.post(reverse('screenshot_delete', kwargs=kwargs))
        self.assertRedirects(response, self.app.get_edit_url())

        # assert that the pointer got deleted
        self.assertEqual(0, Screenshot.objects.all().count())
