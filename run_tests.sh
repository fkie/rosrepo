#!/bin/sh
set -e
nosetests -v --with-coverage --cover-package=rosrepo --cover-erase "$@"
nosetests3 -v --with-coverage --cover-package=rosrepo "$@"

