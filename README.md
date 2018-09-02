[![build status](https://gitlab.com/fdroid/repomaker/badges/master/build.svg)](https://gitlab.com/fdroid/repomaker/commits/master)
[![coverage report](https://gitlab.com/fdroid/repomaker/badges/master/coverage.svg)](https://gitlab.com/fdroid/repomaker/-/jobs)
[![translation status](https://hosted.weblate.org/widgets/f-droid/-/repomaker/svg-badge.svg)](https://hosted.weblate.org/projects/f-droid/repomaker/)

# Installation

## Requirements

Please make sure you have the following requirements installed
before proceeding with the installation. 

### Install

* `pip` for installation of Python 3 dependencies
* `virtualenv` to create a isolated Python environment `apt install `
* Python development and build files for installing/building some dependencies

On Debian, you can simply run this:

`apt install python3-pip python3-wheel python3-dev virtualenv build-essential`

### Runtime

* `keytool` from Java Runtime Environment (JRE)
* `apksigner` or alternatively jarsigner from Java Development Kit (JDK)
* Android Asset Packaging Tool (`aapt`)
* `libmagic` for mime-type detection
* `rsync` to publish repositories
* `git` to publish repositories to git mirrors

On Debian, you can simply run this:

`sudo apt install openjdk-8-jre-headless apksigner aapt libmagic1 rsync git`

## Install into virtual environment

To not mess with other Python libraries you have installed,
we will install repomaker into its own isolated Python environment.

    virtualenv -p /usr/bin/python3 repomaker
    source repomaker/bin/activate
    pip install repomaker[gui]

You should now be able to start by typing:

    repomaker

## Troubleshooting

First check that you really have all dependencies from above installed.

If the installation fails with something about `openssl`,
try to install `libssl-dev` with `apt install libssl-dev`.

If starting repomaker fail with the error ```Could not find `keytool` program.```,
you might run into [this known issue](https://gitlab.com/fdroid/repomaker/issues/192).
Try if `apt install openjdk-8-jdk-headless` fixes it for you.

If the graphical user interface fails to start,
you can try running `repomaker-server` and `repomaker-tasks`.
If that works, you should be able to open [127.0.0.1:8000](http://127.0.0.1:8000/)
in your browser.

# Development

* npm to fetch CSS and JavaScript dependencies `apt install npm`

Then run `npm install` to install these dependencies.

## Translation

* GNU gettext `apt install gettext`

# License

This program is free software: you can redistribute it and/or modify it
under the terms of the [GNU Affero General Public License](/LICENSE)
as published by the Free Software Foundation,
either version 3 of the License,
or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU Affero General Public License for more details.


# Translating

Everything can be translated.  See
[Translation and Localization](https://f-droid.org/docs/Translation_and_Localization)
for more info.

* To update translations, run `./update-translations.sh`.
* To add a new translation, run `python3 manage.py makemessages -l <lg>` where `<lg>` is the language code, e.g. `de`.

[![translation status](https://hosted.weblate.org/widgets/f-droid/-/repomaker/multi-auto.svg)](https://hosted.weblate.org/engage/f-droid/?utm_source=widget)
