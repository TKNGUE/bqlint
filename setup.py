#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

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
    entry_points={
    'console_scripts': [
        'bqlint = bqlint:_main',
        ],
    },
)
