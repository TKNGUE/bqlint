#!/bin/bash

set -e
set -x

echo 'List files from cached directories'
echo 'pip:'
ls $HOME/.cache/pip

if [ "${SKIP_TESTS}" == "true" ]; then
    echo "No need to build bqlint when not running the tests"
else

  # Set up our own virtualenv environment to avoid travis' numpy.
  # This venv points to the python interpreter of the travis build
  # matrix.
  pip install --upgrade pip setuptools
  # Build bqlint in the install.sh script to collapse the verbose
  # build output in the travis output when it succeeds.
  python --version
  python -c "import pytest; print('pytest %s' % pytest.__version__)"

  if [ "${CODECLIMATE_COVERAGE_REPORT}" = "true" ]; then
    pip install codeclimate-test-reporter
  fi

  if [ "${CODECOV_COVERAGE_REPORT}" = "true" ]; then
    pip install codecov
  fi

fi
