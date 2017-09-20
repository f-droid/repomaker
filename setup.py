import os

from setuptools import setup, find_packages

DATA_PREFIX = os.path.join('share', 'repomaker')

packages = find_packages(exclude=['*.tests*'])
print("Packages: %s" % str(packages))

setup(
    name='repomaker',
    version='0.0.2a',
    packages=packages + ['repomaker-static'],
    description='Create F-Droid repositories with ease',
    license='AGPL-3.0',
    # TODO Repomaker Website https://gitlab.com/fdroid/fdroid-website/issues/70
    url='https://gitlab.com/fdroid/repomaker',
    python_requires='>=3',
    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=[
        'django',
        'django-allauth',
        'django-tinymce',
        'django-js-reverse',
        'django-compressor',
        'django-sass-processor',
        'django-hvad>=1.8.0',
        'django-background-tasks>=1.1.9',
        'qrcode',
        'six>=1.9',  # until bleach depends on html5lib>=1.0
        'bleach',
        'python-magic',
        'cryptography>=1.4.0',
        'fdroidserver>=0.8',
    ],

    # List additional groups of dependencies here (e.g. development dependencies).
    # You can install these using the following syntax, for example:
    # $ pip install -e .[dev,test]
    extras_require={
        'gui': [
            'pywebview[qt5]',
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
