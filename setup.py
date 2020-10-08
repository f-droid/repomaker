#!/usr/bin/env python3

import os
import subprocess
import sys

from setuptools import setup, find_packages, Command
from repomaker import VERSION


class RepomakerStaticCheckCommand(Command):
    """Make sure git tag and version match before uploading"""
    user_options = []

    def initialize_options(self):
        """Abstract method that is required to be overwritten"""

    def finalize_options(self):
        """Abstract method that is required to be overwritten"""

    def run(self):
        if not os.path.isdir('repomaker-static'):
            print('ERROR: repomaker-static is missing, run ./pre-release.sh')
            sys.exit(1)

class VersionCheckCommand(Command):
    """Make sure git tag and version match before uploading"""
    user_options = []

    def initialize_options(self):
        """Abstract method that is required to be overwritten"""

    def finalize_options(self):
        """Abstract method that is required to be overwritten"""

    def run(self):
        version = self.distribution.get_version()
        version_git = subprocess.check_output(['git', 'describe', '--tags', '--always']).rstrip().decode('utf-8')
        if version != version_git:
            print('ERROR: Release version mismatch! setup.py (%s) does not match git (%s)'
                  % (version, version_git))
            sys.exit(1)
        print('Upload using: twine upload --sign dist/repomaker-%s.tar.gz' % version)


DATA_PREFIX = os.path.join('share', 'repomaker')

packages = find_packages()
print("Packages: %s" % str(packages))

with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'README.md')) as f:
    long_description = f.read()

setup(
    name='repomaker',
    version=VERSION,
    packages=packages + ['repomaker-static'],
    description='Create F-Droid repositories with ease',
    long_description=long_description,
    long_description_content_type='text/markdown',
    license='AGPL-3.0',
    url='https://f-droid.org/repomaker/',
    python_requires='>=3',
    cmdclass={
        'repomaker_static_check': RepomakerStaticCheckCommand,
        'version_check': VersionCheckCommand,
    },
    setup_requires=[
        'babel',
    ],
    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=[
        'django  >=1.11.29, < 1.12',
        'django-allauth',
        'django-tinymce >=2.6.0, <3',
        'django-js-reverse',
        'django-compressor',
        'django-sass-processor',
        'django-hvad>=1.8.0',
        'django-background-tasks >=1.1.13, <1.2',
        'qrcode',
        'six>=1.9',  # until bleach depends on html5lib>=1.0
        'bleach>=2.1.4',
        'python-magic',
        'cryptography>=1.4.0',
        'fdroidserver >=1.1, < 2.0',
    ],

    # List additional groups of dependencies here (e.g. development dependencies).
    # You can install these using the following syntax, for example:
    # $ pip install -e .[dev,test]
    extras_require={
        'gui': [
            'PyQt5==5.10.0',
            'pywebview[qt5] <3',
        ],
        'test': [
            'pep8',
            'coverage',
            'pylint-django',
        ],
    },

    include_package_data=True,
    package_data={},

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={
        'console_scripts': [
            'repomaker-server = repomaker:runserver',
            'repomaker-tasks = repomaker:process_tasks',
        ],
        'gui_scripts': [
            'repomaker = repomaker.gui:main',
        ],
    },
)
