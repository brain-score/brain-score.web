#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open('README.md') as readme_file:
    readme = readme_file.read()

requirements = [
    "numpy",
    "django",
    "django_compressor",
    "colour",
    "pandas",
    "tqdm",
    "requests",
    "six",
    "psycopg2",
    "boto3",
]

setup(
    name='brain-score.web',
    version='0.1.0',
    description="Brain-Score website.",
    long_description=readme,
    author="Brain-Score team",
    url='https://github.com/brain-score/brain-score.web',
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    license="MIT license",
    zip_safe=False,
    keywords='brain-score',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
)
