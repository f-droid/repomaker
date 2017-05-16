import sys
from importlib import reload

import django.urls
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings, modify_settings

from maker import DEFAULT_USER_NAME


class LoginSingleUserTest(TestCase):

    def test_login(self):
        response = self.client.get('/')
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed(response, 'maker/index.html')

        # verify that default user was logged in automatically
        user = User.objects.get(username=DEFAULT_USER_NAME)
        self.assertEqual(str(user.pk), self.client.session['_auth_user_id'])
        self.assertEqual(user, response.context['request'].user)


@override_settings(SINGLE_USER_MODE=False)
@modify_settings(INSTALLED_APPS={'append': ['allauth', 'allauth.socialaccount']})
class LoginMultiUserTest(TestCase):

    def setUp(self):
        # update URL conf with overridden settings
        reload(sys.modules[settings.ROOT_URLCONF])
        django.urls.clear_url_caches()

    def test_login_redirect(self):
        response = self.client.get('/')
        self.assertRedirects(response, '/accounts/login/?next=/')

    def test_login_get(self):
        response = self.client.get('/accounts/login/?next=/')
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed(response, 'account/login.html')

    def test_login(self):
        # create a new user to log in with
        User.objects.create_user('user2', 'user2@example.org', 'pass')

        # post user credentials into login form
        query = {'login': 'user2', 'password': 'pass', 'next': '/'}
        response = self.client.post('/accounts/login/', query)
        self.assertRedirects(response, '/')

        # assert that user was logged in properly
        user = User.objects.get(username='user2')
        self.assertEqual(str(user.pk), self.client.session['_auth_user_id'])


class MiscTest(TestCase):

    @override_settings(SITE_NOTICE='test site notice')
    def test_site_notice(self):
        # Issue a GET request
        response = self.client.get('/')
        self.assertEqual(200, response.status_code)

        # Check that the rendered context contains the site_notice
        self.assertTrue('site_notice' in response.context)
        self.assertEqual(settings.SITE_NOTICE, response.context['site_notice'])
        self.assertContains(response, settings.SITE_NOTICE)

    def test_site_notice_only_when_set(self):
        # Issue a GET request
        response = self.client.get('/')
        self.assertEqual(200, response.status_code)

        # Check that the rendered context contains a None site_notice
        self.assertTrue('site_notice' in response.context)
        self.assertIsNone(response.context['site_notice'])
