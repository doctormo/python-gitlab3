#!/usr/bin/env python

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name='gitlab3',
    version='0.5.8',
    license='LGPLv3',
    description='GitLab API v3 Python Wrapper.',
    long_description='An incomplete Python client/wrapper for GitLab API v3',
    packages=['gitlab3'],
    author="Alex Van't Hof",
    author_email='alexvh@cs.columbia.edu',
    install_requires=['requests'],
    url='http://github.com/doctormo/python-gitlab3',
    keywords='gitlab api client wrapper',
)
