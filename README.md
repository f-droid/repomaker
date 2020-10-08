[![build status](https://gitlab.com/fdroid/repomaker/badges/master/build.svg)](https://gitlab.com/fdroid/repomaker/commits/master)
[![coverage report](https://gitlab.com/fdroid/repomaker/badges/master/coverage.svg)](https://gitlab.com/fdroid/repomaker/-/jobs)
[![translation status](https://hosted.weblate.org/widgets/f-droid/-/repomaker/svg-badge.svg)](https://hosted.weblate.org/projects/f-droid/repomaker/)

Repomaker needs a maintainer, please adopt me!  Repomaker currently runs on Django 1.11, which went out of security support in July 2020. Please see [#234](https://gitlab.com/fdroid/repomaker/-/issues/233) for more information.

# Installation

There are several different ways to install Repomaker.

## Flatpak

Repomaker is available as Flatpak and
[distributed on Flathub](https://flathub.org/apps/details/org.fdroid.Repomaker).
Once you got [Flatpak installed on your system](https://flatpak.org/setup/),
either go to your system's app store or execute the following commands:
```bash
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install flathub org.fdroid.Repomaker
```

## On a server / Docker

Note that you can run Repomaker on a server and make use of its
multi user functionality.
See [Docker docs](https://gitlab.com/fdroid/repomaker/tree/master/docker)
and the
[general docs](https://gitlab.com/fdroid/repomaker/tree/master/doc)
for more information on that topic.


## PyPi

If you don't want or can't install Repomaker with one of the mentioned
methods, you can install it with _pip_ from PyPi.

### Requirements

Please make sure you have the following requirements installed
before proceeding with the installation. 

#### Install

* `pip` for installation of Python 3 dependencies
* `virtualenv` to create an isolated Python environment
* Python development and build files for installing/building some dependencies

On Debian, you can simply run this:

`apt install python3-pip python3-wheel python3-dev virtualenv build-essential`

#### Runtime

* `keytool` from Java Runtime Environment (JRE)
* `jarsigner` from Java JDK for signing the repo indexes
* `libmagic` for mime-type detection
* `rsync` to publish repositories
* `git` to publish repositories to git mirrors

On Debian, you can simply run this:

```
sudo apt install fdroidserver libmagic1 rsync git \
    python3-pyqt5.qtwebengine python3-pyqt5.qtwebkit
```

### Install into virtual environment

To not mess with other Python libraries you have installed,
we will install repomaker into its own isolated Python environment.

    virtualenv -p /usr/bin/python3 repomaker
    source repomaker/bin/activate
    pip install repomaker[gui]

You should now be able to start by typing:

    repomaker


### Troubleshooting

First check that you really have all dependencies from above installed.

If the installation fails with something about `openssl`,
try to install `libssl-dev` with `apt install libssl-dev`.

If the graphical user interface fails to start,
you can try running `repomaker-server` and `repomaker-tasks`.
If that works, you should be able to open [127.0.0.1:8000](http://127.0.0.1:8000/)
in your browser.


# Development

To work on repomaker, you need _npm_ to fetch CSS and JavaScript dependencies: `apt install npm`.

Then run `npm install` to install these dependencies.

If you want to run repomaker in your browser rather then using the GUI,
you can start it like this:

    virtualenv -p /usr/bin/python3 repomaker
    source repomaker/bin/activate
    ./setup.sh
    ./run.sh

## Vagrant VM

There also a Vagrant setup based on the GitLab CI setup, it is a quick
way to get a development setup.  First, set up Vagrant on your machine,
then run:

```console
$ cd repomaker
$ vagrant up
$ vagrant ssh
vagrant@basebox-buster64:~$ ip a | sed -En 's,.*inet +(192\.168\.[0-9]+\.[0-9]+).*,open http://\1:8000,p'
open http://192.168.121.37:8000
vagrant@basebox-buster64:~$ cd $CI_PROJECT_DIR
vagrant@basebox-buster64:/builds/fdroid/repomaker$ ./tests/test-units.sh
```


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
