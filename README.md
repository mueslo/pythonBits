This is a sloppy fork of [pythonBits](https://github.com/mueslo/pythonbits) that
fixes compatibility issues with recent tools (e.g. mediainfo and tvdb). It's not
a proper fork, I just fix bugs as I find them.

Everything should work like it does with mueslo/pythonBits, except for the
installation.

## Installation

I recommend [pipx](https://pipxproject.github.io/pipx/), which installs Python
packages with all dependencies in a virtual environment in
`~/.local/pipx/<package name>` and thus makes it very easy to uninstall them. To
uninstall pythonBits with pip, you need to do something like this:

```sh
pip3 uninstall -y appdirs attrdict attrs babelfish boto certifi chardet configparser diskcache future guessit idna imdbpie Logbook pip pkg-resources progressbar2 pymediainfo pyreadline python-dateutil python-utils pythonbits rebulk requests requests-cache setuptools six trans tvdb-api Unidecode urllib3 wheel
```

But this might break other Python packages that share dependencies with
pythonBits. This issue doesn't exist with pipx:

```sh
$ # If possible, install pipx with your package manager, otherwise use pip
$ pip3 install --user pipx
$ # Install pythonBits
$ pipx install --spec git+https://github.com/plotski/pythonBits.git pythonBits
$ # You must also specify the git repository when upgrading
$ pipx upgrade --spec git+https://github.com/plotski/pythonBits.git pythonBits
$ # Uninstalling is straightforward
$ pipx uninstall pythonBits
```

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
