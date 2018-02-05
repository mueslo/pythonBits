# pythonBits
#### A Python description generator for movies and TV shows

## Install
1. Install pythonBits in one of the following ways
  * install via `pip2 install pythonbits`
  * clone and `pip2 install .`
  * clone, `pip2 install -r requirements.txt` and run as `python -m pythonbits` instead of `pythonbits`

2. Install mediainfo, ffmpeg and mktorrent such that they are accessible from $PATH

## Usage
```
usage: pythonbits [-h] [-v] [-c {tv,movie}] [-i] [-t] [-s] [-d] [-b]
                  [-f FIELD [FIELD ...]] [--num-cast NUM_CAST]
                  [--num-screenshots NUM_SCREENSHOTS] [--dry-run]
                  PATH [TITLE]
```
Use `pythonbits --help` to get a more extensive usage overview

## Examples
pythonBits will attempt to guess as much information as possible from the filename. Unlike in previous releases, explicitly specifying a category or title is usually not necessary. PATH can also reference a directory, e.g. for season packs.

In most cases it is enough to just run `pythonbits <path>`

Print mediainfo: `pythonbits -i <path>`, equivalent to `pythonbits -f mediainfo <path>`
Make screenshots, but don't upload: `pythonbits -s --dry-run <path>`
Write a description: `pythonbits -d <path>`
Generate complete submission: `pythonbits -b <path>` (Note: this is an untested, experimental feature)

In case the media title and type cannot be guessed from the path alone, you can explicitly specify them, e.g. `pythonbits <path> "Doctor Who (2005) S06"`or `pythonbits <path> -c movie`.

You can also import pythonbits to use in your own Python projects. For reference on how to best use it, take a look at `__main__.py`. Once you have created an appropriate `Submission` instance `s`, you can access any desired feature, for example `s['title']`, `s['tags']` or `s['cover']`.
