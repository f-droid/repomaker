from pkg_resources import Requirement, resource_filename
from repomaker.settings import *


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'postgres',
        'USER': 'postgres',
        'HOST': 'db',
        'PORT': 5432,
    }
}

SINGLE_USER_MODE = False

LOGIN_REDIRECT_URL = "/"
# http://django-allauth.readthedocs.io/en/latest/installation.html
INSTALLED_APPS += [
    'allauth',
    'allauth.socialaccount',
    # 'allauth.socialaccount.providers.amazon',
    # 'allauth.socialaccount.providers.baidu',
    # 'allauth.socialaccount.providers.bitbucket_oauth2',
    # 'allauth.socialaccount.providers.dropbox_oauth2',
    # 'allauth.socialaccount.providers.facebook',
    # 'allauth.socialaccount.providers.github',
    # 'allauth.socialaccount.providers.gitlab',
    # 'allauth.socialaccount.providers.google',
    # 'allauth.socialaccount.providers.linkedin_oauth2',
    'allauth.socialaccount.providers.openid',
    # 'allauth.socialaccount.providers.reddit',
    # 'allauth.socialaccount.providers.slack',
    # 'allauth.socialaccount.providers.stackexchange',
    # 'allauth.socialaccount.providers.twitter',
    # 'allauth.socialaccount.providers.weibo',
]
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
)
ACCOUNT_FORMS = {
    'login': 'repomaker.views.RmLoginForm',
    'reset_password': 'repomaker.views.RmResetPasswordForm',
    'signup': 'repomaker.views.RmSignupForm',
}
ACCOUNT_EMAIL_VERIFICATION = "none"

# TODO
#DEFAULT_REPO_STORAGE = [
#    (os.path.join(DATA_DIR, 'repos'), 'http://127.0.0.1/repos/'),
#]

