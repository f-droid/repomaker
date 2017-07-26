import os

from setuptools import setup, find_packages

DATA_PREFIX = os.path.join('share', 'repomaker')

packages = find_packages(exclude=['*.tests*'])
print("Packages: %s" % str(packages))


def get_data_files_in(directory):
    pairs = []
    for (rel_path, directories, filenames) in os.walk(directory):
        files = []
        for filename in filenames:
            files.append(os.path.join(rel_path, filename))
        if len(files) > 0:
            pairs.append((os.path.join(DATA_PREFIX, rel_path), files))
    return pairs


setup(
    version='0.0.1a1',
    packages=packages,
    include_package_data=True,
    python_requires='>=3',
    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=[
        'django',
        'django-allauth',
        'django-tinymce',
        'django-compressor',
        'django-sass-processor',
        'django-hvad>=1.8.0',
        'django-background-tasks>=1.1.9',
        'qrcode',
        'six>=1.9',  # until bleach depends on html5lib>=1.0
        'bleach',
        'python-magic',
        'cryptography>=1.4.0',
        'fdroidserver',
    ],
    # TODO this fdroidserver dependency doesn't seem to work :(
    dependency_links=[
        'git+https://gitlab.com/fdroid/fdroidserver.git@0be224b3e0c7b82b36bdd3c6bca07e0e6cb4a023#egg=fdroidserver',
    ],

    # List additional groups of dependencies here (e.g. development dependencies).
    # You can install these using the following syntax, for example:
    # $ pip install -e .[dev,test]
    extras_require={
        'test': [
            'pep8',
            'coverage',
            'pylint-django',
        ],
    },

    # package_data={},

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.5/distutils/setupscript.html#installing-additional-files # noqa
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    data_files=get_data_files_in('data/static/') + [
        (os.path.join(DATA_PREFIX, 'data', 'media'), [
            'data/media/default-app-icon.png',
            'data/media/default-repo-icon.png',
        ])
    ],

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={
        'console_scripts': [
            'repomaker-server = repomaker:runserver',
            'repomaker-tasks = repomaker:process_tasks',
        ],
        # TODO 'gui_scripts': []
    },
)
