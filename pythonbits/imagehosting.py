# -*- coding: utf-8 -*-
from .config import config

from .imgur import ImgurUploader
from .ptpimg import PtpImgUploader

config.register('ImageHosting', 'provider',
                "Enter a provider for image hosting, supported options are "
                "ptpimg or imgur",
                ask=True)


def upload_files(images):
    provider = config.get('ImageHosting', 'provider')
    if provider.lower() == 'imgur':
        return ImgurUploader().upload(images)
    elif provider.lower() == 'ptpimg':
        return PtpImgUploader().upload_files(*images)


def upload_urls(images):
    provider = config.get('ImageHosting', 'provider')
    if provider.lower() == 'imgur':
        return ImgurUploader().upload(images)
    elif provider.lower() == 'ptpimg':
        return PtpImgUploader().upload_urls(images)
