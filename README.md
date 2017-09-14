[![build status](https://gitlab.com/fdroid/repomaker/badges/master/build.svg)](https://gitlab.com/fdroid/repomaker/commits/master)
[![coverage report](https://gitlab.com/fdroid/repomaker/badges/master/coverage.svg)](https://gitlab.com/fdroid/repomaker/-/jobs)
[![translation status](https://hosted.weblate.org/widgets/f-droid/-/repomaker/svg-badge.svg)](https://hosted.weblate.org/projects/f-droid/repomaker/)

# Warning

This tool is still under heavy development.
**Don't use it in production, yet!**
Database migrations are not yet supported, use `purge.sh` to purge your data
and start from scratch after each update.

# Requirements

## Install

* pip for installation of Python 3 dependencies `apt install python3-pip`

## Runtime

* keytool from Java Runtime Environment (JRE)
* apksigner or alternatively jarsigner from Java Development Kit (JDK)
* Android Asset Packaging Tool (aapt)
* libmagic for mime-type detection
* rsync to publish repositories
* git to publish repositories to git mirrors

On Debian, you can simply run this:

`sudo apt install openjdk-8-jre-headless apksigner aapt libmagic1 rsync git`

## Development

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
