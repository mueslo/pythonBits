# -*- coding: utf-8 -*-
from io import open
from os import path, chmod, makedirs

import configparser
import getpass
import appdirs

from . import __title__ as appname
from .logging import log

CONFIG_NAME = appname.lower() + '.cfg'
CONFIG_DIR = appdirs.user_config_dir(appname.lower())
CONFIG_PATH = path.join(CONFIG_DIR, CONFIG_NAME)
CONFIG_VERSION = 1

if not path.exists(CONFIG_DIR):
    makedirs(CONFIG_DIR, 0o700)


class Config():
    registry = {}

    def __init__(self, config_path=None):
        self.config_path = config_path or CONFIG_PATH
        self._config = configparser.ConfigParser()

    def register(self, section, option, query, ask=False, getpass=False):
        self.registry[(section, option)] = {
            'query': query, 'ask': ask, 'getpass': getpass}

        # todo: ask to remember choice if save is declined

    def _write(self):
        with open(self.config_path, 'w') as configfile:
            self._config.write(configfile)
        chmod(self.config_path, 0o600)

    def set(self, section, option, value):
        if not self._config.has_section(section):
            self._config.add_section(section)
        self._config.set(section, option, value)
        self._write()

    def get(self, section, option, default='dontguessthis'):
        self._config.read(self.config_path)
        try:
            return self._config.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):

            try:
                reg_option = self.registry[(section, option)]
            except KeyError:
                if default != 'dontguessthis':  # dirty hack
                    return default
                else:
                    raise

            if reg_option['getpass']:
                value = getpass.getpass(reg_option['query'] + ": ")
            else:
                value = input(reg_option['query'] + ": ").strip()

            if (reg_option['ask'] and
                input(
                    'Would you like to save this value in {}? [Y/n] '.format(
                        self.config_path)).lower() == 'n'):
                return value

            self.set(section, option, value)

            return value


def backup(config):
    from datetime import datetime
    t = datetime.now()

    p = config.config_path
    config.config_path = (config.config_path + "." +
                          t.strftime("%Y-%m-%dT%H-%M-%S") + '.bak')
    config._write()
    log.notice('Old config backed up at {}', config.config_path)
    config.config_path = p


def imgur_api_change(config):
    if config.get('Imgur', 'client_id', None) is not None:
        config._config.remove_section('Imgur')
        config._write()
    else:
        log.warning('section already removed')


def migrate_config(config):
    migrations = {0: (1, imgur_api_change)}
    version_args = lambda v: ('General', 'version', v)  # noqa: E731

    cur = int(config.get(*version_args(0)))
    if cur in migrations:
        backup(config)
        while True:
            cur = int(config.get(*version_args(0)))
            try:
                new, mig = migrations[cur]
            except KeyError:
                break
            else:
                log.notice('Migrating config from {} to {}'.format(cur, new))
                mig(config)
                config.set(*version_args(str(new)))


config = Config()
migrate_config(config)
