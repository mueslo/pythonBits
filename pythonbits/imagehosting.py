# -*- coding: utf-8 -*-
from .config import config

from .imgur import ImgurUploader
from .ptpimg import PtpImgUploader

config.register('ImageHosting', 'provider',
                "Enter a provider for image hosting, supported options are "
                "ptpimg or imgur",
                ask=True)


def get_provider():
    provider = config.get('ImageHosting', 'provider')
    if provider.lower() == 'imgur':
        return ImgurUploader
    elif provider.lower() == 'ptpimg':
        return PtpImgUploader
    raise Exception('Unknown image hosting provider in config {}'.format(
        config.config_path
        ))


def upload(*images, uploader=None):
    if not uploader:
        provider = get_provider()
        uploader = provider()
    upload_gen = uploader.upload(*images)
    if len(images) == 1:
        return next(upload_gen)
    return list(upload_gen)
