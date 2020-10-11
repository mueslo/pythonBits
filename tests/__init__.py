import os
from unittest import mock
import pythonbits.config as config

dir_path = os.path.dirname(os.path.realpath(__file__))
config.config = config.Config(dir_path + '/pythonbits.cfg')
config.config._write = mock.MagicMock()
