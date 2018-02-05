# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
import codecs
import re
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with codecs.open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

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
    #long_description=long_description,  # Optional
    #url='https://github.com/mueslo/Pythonbits',  # Optional
    #author_email='mueslo@mueslo.de',  # Optional
    #keywords='sample setuptools development',  # Optional
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    entry_points={
        'console_scripts': [
            'pythonbits = pythonbits.__main__:main'
        ]
    },
) 
