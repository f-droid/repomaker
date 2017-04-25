from unittest import TestCase

from django.conf import settings
from django.test import override_settings, Client

# FIXME This file probably needs to be split up when we start testing more views
#       https://docs.djangoproject.com/en/1.11/topics/testing/tools/


class SimpleTest(TestCase):

    def setUp(self):
        self.client = Client()

    @override_settings(SITE_NOTICE='test site notice')
    def test_site_notice(self):
        # Issue a GET request
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        # Check that the rendered context contains the site_notice
        self.assertTrue('site_notice' in response.context)
        self.assertEqual(settings.SITE_NOTICE, response.context['site_notice'])

    def test_site_notice_only_when_set(self):
        # Issue a GET request
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        # Check that the rendered context contains a None site_notice
        self.assertTrue('site_notice' in response.context)
        self.assertIsNone(response.context['site_notice'])
