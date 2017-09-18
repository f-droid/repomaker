# Building Debian Package

As of writing, not all dependencies are in Debian.
That is why a virtualenv approach is used that is shipping various dependencies without the package.

Before building the package, call the following command to prepare all non-code files for inclusion:

    ./pre-release.sh

## Using dpkg-buildpackage

In the repository root execute the following command to build a Debian package.

    dpkg-buildpackage -b -us -uc

## Using pbuilder (recommended)

It is advised to build packages in a minimal chroot instead,
so dependencies can be detected and added properly.

### Setup

Install pbuilder:

    sudo apt install pbuilder

Enable network access during builds to download python dependencies:

    echo USENETWORK=yes >> ~/.pbuilderrc

Create chroot environment image:

    sudo pbuilder create --distribution stable

### Building

Build the package:

    pdebuild

If everything goes well, you should find the Debian package in

    /var/cache/pbuilder/result/
