#!/usr/bin/env python

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name='gitlab3',
    version='0.1.2',
    license='LGPLv3a',
    description='GitLab API v3 Python Wrapper.',
    packages=['gitlab3'],
    author="Alex Van't Hof",
    author_email='alexvh@cs.columbia.edu',
    install_requires=['requests'],
    url='http://github.com/alexvh/python-gitlab3',
)
