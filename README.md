[![build status](https://gitlab.com/fdroid/repomaker/badges/master/build.svg)](https://gitlab.com/fdroid/repomaker/commits/master)
[![coverage report](https://gitlab.com/fdroid/repomaker/badges/master/coverage.svg)](https://gitlab.com/fdroid/repomaker/commits/master)

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
  `apt install openjdk-8-jre-headless`
* apksigner `apt install apksigner` or alternatively jarsigner from Java Development Kit (JDK)
  `apt install openjdk-8-jdk`
* Android Asset Packaging Tool (aapt) `apt install aapt`
* libmagic for mime-type detection `apt install libmagic1`

## Development

* npm to fetch CSS and JavaScript dependencies `apt install npm`

Then run `npm install` to install these dependencies.

## Translation

* GNU gettext `apt install gettext`

# Translating

To update translations,
run `./update-translations.sh`.

To add a new translation,
run `python3 manage.py makemessages -l <lg>`
where `<lg>` is the language code, e.g. `de`.

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
