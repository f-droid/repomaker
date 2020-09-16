#!/usr/bin/env bash

pylint=pylint
if which pylint3; then
    pylint=pylint3
fi
$pylint --disable=C,R,fixme repomaker
