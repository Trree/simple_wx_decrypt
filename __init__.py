"""
微信数据解密工具包

完美复刻 EchoTrace 的 Go 解密核心代码
支持数据库和图片解密
"""

__version__ = '1.0.0'
__author__ = 'EchoTrace Python Port'

from .decrypt_core import (
    WeChatDBDecryptor,
    DecryptError,
    InvalidKeyError,
    HMACVerificationError,
)

from .image_decrypt import (
    WeChatImageDecryptor,
    ImageDecryptError,
)

__all__ = [
    'WeChatDBDecryptor',
    'WeChatImageDecryptor',
    'DecryptError',
    'InvalidKeyError',
    'HMACVerificationError',
    'ImageDecryptError',
]
