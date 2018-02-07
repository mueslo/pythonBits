# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
import codecs
import re
from os import path

here = path.abspath(path.dirname(__file__))


def read(*parts):
    with codecs.open(path.join(here, *parts), 'r') as fp:
        return fp.read()


def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


setup(
    name='pythonbits',
    version=find_version("pythonbits", "__init__.py"),
    description="A pretty printer for media",
    license='GPLv3',
    url='https://github.com/mueslo/pythonBits',
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    install_requires=[
        "imdbpie~=5.2",
        "requests~=2.18",
        "tvdb-api~=1.9",
        "attrdict~=2.0",
        "appdirs~=1.4",
        "pymediainfo~=2.2",
        "guessit~=2.1"],
    python_requires="~=2.7",
    classifiers=[
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2 :: Only",
        "Programming Language :: Python :: 2.7",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Topic :: Internet",
        "Topic :: Multimedia",
        "Topic :: Utilities"],
    entry_points={
        'console_scripts': [
            'pythonbits = pythonbits.__main__:main'
        ]
    },
)
