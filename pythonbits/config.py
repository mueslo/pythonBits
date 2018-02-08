# -*- coding: utf-8 -*-
from os import path, chmod, mkdir

import ConfigParser
import getpass
import appdirs

from . import __title__ as appname

CONFIG_NAME = appname.lower() + '.cfg'
CONFIG_DIR = appdirs.user_config_dir(appname.lower())
CONFIG_PATH = path.join(CONFIG_DIR, CONFIG_NAME)

if not path.exists(CONFIG_DIR):
    mkdir(CONFIG_DIR, 0700)


class Config():
    registry = {}

    def __init__(self, config_path=None):
        self.config_path = config_path or CONFIG_PATH
        self._config = ConfigParser.SafeConfigParser()

    def register(self, section, option, query, ask=False, getpass=False):
        self.registry[(section, option)] = {
            'query': query, 'ask': ask, 'getpass': getpass}

        # todo: ask to remember choice if save is declined

    def _write(self):
        with open(self.config_path, 'wb') as configfile:
            self._config.write(configfile)
        chmod(self.config_path, 0600)

    def set(self, section, option, value):
        self._config.set(section, option, value)
        self._write()

    def get(self, section, option, default='dontguessthis'):
        self._config.read(self.config_path)
        try:
            return self._config.get(section, option)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):

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
                value = raw_input(reg_option['query'] + ": ").strip()

            if (reg_option['ask'] and
                raw_input(
                    'Would you like to save this value in {}? [Y/n] '.format(
                        self.config_path)).lower() == 'n'):
                return value

            if not self._config.has_section(section):
                self._config.add_section(section)
            self._config.set(section, option, value)

            self._write()

            return value


config = Config()
