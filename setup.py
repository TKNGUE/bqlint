#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import find_packages
from setuptools import setup
from setuptools.command.test import test as TestCommand
import sys


class PyTest(TestCommand):
    """
    """
    user_options = [
        ('cov=', '-', "coverage target."),
        ('pdb', '-', "start the interactive Python debugger on errors."),
        ('pudb', '-', "start the PuDB debugger on errors."),
        ('quiet', 'q', "decrease verbosity."),
        ('verbose', 'v', "increase verbosity."),
        ('pep8', '-', "pep8 check"),
        ('doctest-modules', '-', "run doctests in all .py modules"),
    ]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        # default option values
        self.cov = 'bqlint'
        self.pdb = False
        self.quiet = False
        self.verbose = True
        self.pep8 = True
        self.doctest_modules = False
        self.test_args = ['']
        self.test_suite = True

    def finalize_options(self):
        TestCommand.finalize_options(self)

    def run_tests(self):
        import pytest

        # default options

        # if cov option is specified, option is replaced.
        if self.cov:
            self.test_args += ["--cov={0}".format(self.cov)]

        if self.pdb:
            self.test_args += ["--pdb"]
        if self.quiet:
            self.test_args += ["--quiet"]
        if self.verbose:
            self.test_args += ["--verbose"]
        if self.pep8:
            self.test_args += ["--pep8"]
        if self.doctest_modules:
            self.test_args += ["--doctest-modules"]

        print("executing 'pytest {0}'".format(" ".join(self.test_args)))
        print('')
        errno = pytest.main(self.test_args)
        sys.exit(errno)


setup(
    name='bqlint',
    version='0.0.1',
    description="A linter for BigQuery's Standard SQL",
    author='TKNGUE',
    license='MIT',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'sqlparse'
    ],
    extras_require={
        'dev': [
            'ipdb',
            'pep8',
        ],
    },
    tests_require=[
        # to report coverage to codecov.io
        'coverage==4.3.4',
        'pytest==3.2.2',
        'pytest-cov==2.5.1',
        'pytest-faker==2.0.0',
        'pytest-mock==1.6.3',
        'pytest-pep8==1.0.6',
    ],
    cmdclass={
        'test': PyTest,
    },
    entry_points={
        'console_scripts': [
            'bqlint = bqlint:_main',
        ],
    },
)
