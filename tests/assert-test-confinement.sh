#!/usr/bin/env bash
set -e
[ ! -d "private_repo" ] || (echo "Error: Tests wrote in private_repo" && exit 1)
[ ! -d "media/user_1" ] || (echo "Error: Tests wrote in media/user_1" && exit 1)
[ ! -d "media/user_2" ] || (echo "Error: Tests wrote in media/user_2" && exit 1)
exit 0
