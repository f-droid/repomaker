#!/usr/bin/env bash

./tests/test-pep8.sh &&
./tests/test-pylint.sh &&
./tests/test-units.sh &&
echo "All tests ran successfully! \o/"
