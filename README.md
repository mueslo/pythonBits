# pythonBits
[![GitHub release](https://img.shields.io/github/release/mueslo/pythonbits.svg)](https://GitHub.com/mueslo/pythonBits/releases/)
[![PyPI version](https://img.shields.io/pypi/v/pythonbits.svg)](https://pypi.python.org/pypi/pythonbits/)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/pythonbits.svg)](https://pypi.python.org/pypi/pythonbits/)
[![GitHub commits since release](https://img.shields.io/github/commits-since/mueslo/pythonbits/latest.svg)](https://github.com/mueslo/pythonBits/commits/master)
[![GitHub license](https://img.shields.io/github/license/mueslo/pythonbits.svg)](https://github.com/mueslo/pythonbits/blob/master/LICENSE)
[![Build Status](https://img.shields.io/travis/mueslo/pythonBits.svg)](https://travis-ci.org/mueslo/pythonBits)
#### A Python description generator for movies and TV shows

## Install
1. (Optional, highly recommended) Set up a virtualenv to avoid polluting your system with dependencies.
  - with virtualenvwrapper: `mkvirtualenv pythonbits`
    - activate the virtualenv with `workon pythonbits`
2. Install pythonBits in one of the following ways
  - install via `pip install pythonbits`
  - clone and `pip install .`
  - (dev) clone, install requirements from setup.py and run as `python -m pythonbits` instead of `pythonbits`
3. Install mediainfo, ffmpeg and mktorrent>=1.1 such that they are accessible for pythonBits
  - you can also manually specify things such as the torrent file or screenshots, this will prevent the programs from being called, removing the dependency

If you don't want to use a virtualenv but keep system pollution with PyPI packages to a minimum, install via `pip install --user`. For more information, visit [this site](https://packaging.python.org/guides/installing-using-pip-and-virtualenv/).

## Usage
```
usage: pythonbits [-h] [--version] [-v] [-c {tv,movie}] [-u FIELD VALUE] [-i]
                  [-t] [-s] [-d] [-b] [-f FIELD [FIELD ...]]
                  [--num-cast NUM_CAST] [--num-screenshots NUM_SCREENSHOTS]
                  PATH [TITLE]
```
Use `pythonbits --help` to get a more extensive usage overview

## Examples
pythonBits will attempt to guess as much information as possible from the filename. Unlike in previous releases, explicitly specifying a category or title is usually not necessary. PATH can also reference a directory, e.g. for season packs.

In most cases it is enough to just run `pythonbits <path>` to generate a media description. If running the desired features requires uploading data to remote servers, you will be prompted to confirm this finalization before it occurs.

* Print mediainfo: `pythonbits -i <path>`, equivalent to `pythonbits -f mediainfo <path>`
* Make screenshots: `pythonbits -s <path>`
* Write a description: `pythonbits -d <path>`
* Make a torrent file: `pythonbits -t <path>`
* Generate complete submission and post it: `pythonbits -b <path>` (Note: YOU are responsible for your uploads)
* Generate complete submission, use supplied torrent file and tags: `pythonbits -b -u torrentfile <torrentfile> -u tags "whatever,tags.you.like" <path>`

In case the media title and type cannot be guessed from the path alone, you can explicitly specify them, e.g. `pythonbits <path> "Doctor Who (2005) S06"`or `pythonbits <path> -c movie`.

You can increase the verbosity of log messages printed to the screen by appending `-v`. This would print `INFO` messages. To print `DEBUG` messages, append twice, i.e. `-vv`.

You can also import pythonbits to use in your own Python projects. For reference on how to best use it, take a look at `__main__.py`. Once you have created an appropriate `Submission` instance `s`, you can access any desired feature, for example `s['title']`, `s['tags']` or `s['cover']`.
