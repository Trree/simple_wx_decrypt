"""
微信图片解密模块
支持 V3 和 V4 版本的 .dat 文件解密
完美复刻 lib/services/image_decrypt_core.dart 的实现
"""

import struct
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


class ImageDecryptError(Exception):
    """图片解密错误"""
    pass


class WeChatImageDecryptor:
    """
    微信图片解密器

    支持格式：
    - V3: 简单 XOR 加密
    - V4-V1: 文件签名 0x07 0x08 0x56 0x31 0x08 0x07
    - V4-V2: 文件签名 0x07 0x08 0x56 0x32 0x08 0x07
    """

    # V4 文件签名
    V4_V1_SIGNATURE = bytes([0x07, 0x08, 0x56, 0x31, 0x08, 0x07])
    V4_V2_SIGNATURE = bytes([0x07, 0x08, 0x56, 0x32, 0x08, 0x07])

    # 默认 AES 密钥（V4-V1 版本）
    DEFAULT_V1_AES_KEY = b'cfcd208495d565ef'

    @staticmethod
    def get_dat_version(file_path: str) -> int:
        """
        检测 .dat 文件版本

        Args:
            file_path: 文件路径

        Returns:
            0: V3 版本（简单 XOR）
            1: V4-V1 版本（AES + XOR）
            2: V4-V2 版本（AES + XOR）

        Raises:
            ImageDecryptError: 文件不存在或读取失败
        """
        path = Path(file_path)
        if not path.exists():
            raise ImageDecryptError(f"文件不存在: {file_path}")

        try:
            with open(file_path, 'rb') as f:
                signature = f.read(6)

            if len(signature) < 6:
                return 0

            if signature == WeChatImageDecryptor.V4_V1_SIGNATURE:
                return 1
            elif signature == WeChatImageDecryptor.V4_V2_SIGNATURE:
                return 2
            else:
                return 0

        except Exception as e:
            raise ImageDecryptError(f"读取文件失败: {e}")

    @staticmethod
    def decrypt_dat_v3(file_path: str, xor_key: int) -> bytes:
        """
        解密 V3 版本的 .dat 文件（简单 XOR）

        对应 Dart 代码：image_decrypt_core.dart:33-40

        Args:
            file_path: 输入文件路径
            xor_key: XOR 密钥（0-255）

        Returns:
            解密后的数据

        Raises:
            ImageDecryptError: 解密失败
        """
        try:
            with open(file_path, 'rb') as f:
                data = f.read()

            # XOR 解密
            result = bytearray(len(data))
            for i in range(len(data)):
                result[i] = data[i] ^ xor_key

            return bytes(result)

        except Exception as e:
            raise ImageDecryptError(f"V3 解密失败: {e}")

    @staticmethod
    def decrypt_dat_v4(
        file_path: str,
        xor_key: int,
        aes_key: Optional[bytes] = None
    ) -> bytes:
        """
        解密 V4 版本的 .dat 文件（AES-ECB + XOR）

        对应 Dart 代码：image_decrypt_core.dart:42-111

        文件格式：
        [0x00-0x05]: 签名（6 字节）
        [0x06-0x09]: AES 加密数据大小（Little-endian，4 字节）
        [0x0A-0x0D]: XOR 加密数据大小（Little-endian，4 字节）
        [0x0E]: 保留字节
        [0x0F...]: 数据部分
            - AES 加密数据（需要 16 字节对齐）
            - 原始数据（未加密）
            - XOR 加密数据

        Args:
            file_path: 输入文件路径
            xor_key: XOR 密钥（0-255）
            aes_key: AES 密钥（16 字节），默认使用 V1 密钥

        Returns:
            解密后的数据

        Raises:
            ImageDecryptError: 解密失败
        """
        if aes_key is None:
            aes_key = WeChatImageDecryptor.DEFAULT_V1_AES_KEY

        if len(aes_key) != 16:
            raise ImageDecryptError(f"AES 密钥必须是 16 字节，实际: {len(aes_key)}")

        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()

            # 检查文件大小
            if len(file_data) < 0xF:
                raise ImageDecryptError("文件太小，无法解析")

            # 解析文件头（15 字节）
            header = file_data[:0xF]
            data = file_data[0xF:]

            # 提取大小信息（Little-endian）
            aes_size = struct.unpack('<I', header[6:10])[0]
            xor_size = struct.unpack('<I', header[10:14])[0]

            # 计算 AES 数据的对齐大小（16 字节对齐）
            aligned_aes_size = aes_size + (16 - (aes_size % 16)) if aes_size % 16 != 0 else aes_size

            if aligned_aes_size > len(data):
                raise ImageDecryptError(f"文件格式异常：AES 数据长度 ({aligned_aes_size}) 超过文件实际长度 ({len(data)})")

            # 步骤 1：AES-ECB 解密
            aes_encrypted_data = data[:aligned_aes_size]
            unpadded_data = b''

            if len(aes_encrypted_data) > 0:
                # 使用 AES-ECB 模式解密
                cipher = Cipher(
                    algorithms.AES(aes_key),
                    modes.ECB(),
                    backend=default_backend()
                )
                decryptor = cipher.decryptor()
                decrypted_data = decryptor.update(aes_encrypted_data) + decryptor.finalize()

                # 去除 PKCS7 填充
                unpadded_data = WeChatImageDecryptor._remove_pkcs7_padding(decrypted_data)

            # 步骤 2：处理剩余数据
            remaining_data = data[aligned_aes_size:]

            if xor_size < 0 or xor_size > len(remaining_data):
                raise ImageDecryptError(f"文件格式异常：XOR 数据长度 ({xor_size}) 不合法")

            # 分离原始数据和 XOR 加密数据
            if xor_size > 0:
                raw_length = len(remaining_data) - xor_size
                if raw_length < 0:
                    raise ImageDecryptError("文件格式异常：原始数据长度小于 XOR 长度")

                raw_data = remaining_data[:raw_length]
                xor_encrypted_data = remaining_data[raw_length:]

                # XOR 解密
                xored_data = bytearray(len(xor_encrypted_data))
                for i in range(len(xor_encrypted_data)):
                    xored_data[i] = xor_encrypted_data[i] ^ xor_key
                xored_data = bytes(xored_data)
            else:
                raw_data = remaining_data
                xored_data = b''

            # 步骤 3：拼接结果
            result = unpadded_data + raw_data + xored_data

            return result

        except ImageDecryptError:
            raise
        except Exception as e:
            raise ImageDecryptError(f"V4 解密失败: {e}")

    @staticmethod
    def _remove_pkcs7_padding(data: bytes) -> bytes:
        """
        去除 PKCS7 填充

        对应 Dart 代码：image_decrypt_core.dart:121-140

        Args:
            data: 填充后的数据

        Returns:
            去除填充后的数据

        Raises:
            ImageDecryptError: 填充格式非法
        """
        if len(data) == 0:
            raise ImageDecryptError("解密结果为空，填充非法")

        # 获取填充长度
        padding_length = data[-1]

        # 验证填充长度
        if padding_length == 0 or padding_length > 16 or padding_length > len(data):
            raise ImageDecryptError(f"PKCS7 填充长度非法: {padding_length}")

        # 验证填充内容
        for i in range(len(data) - padding_length, len(data)):
            if data[i] != padding_length:
                raise ImageDecryptError(f"PKCS7 填充内容非法: 期望 {padding_length}，实际 {data[i]}")

        # 返回去除填充后的数据
        return data[:-padding_length]

    @staticmethod
    def auto_decrypt_dat(
        input_path: str,
        output_path: str,
        xor_key: int,
        aes_key: Optional[bytes] = None
    ) -> str:
        """
        自动检测版本并解密 .dat 文件

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            xor_key: XOR 密钥（0-255）
            aes_key: AES 密钥（16 字节），仅用于 V4 版本

        Returns:
            版本信息字符串

        Raises:
            ImageDecryptError: 解密失败
        """
        # 检测版本
        version = WeChatImageDecryptor.get_dat_version(input_path)

        # 根据版本解密
        if version == 0:
            # V3 版本
            decrypted_data = WeChatImageDecryptor.decrypt_dat_v3(input_path, xor_key)
            version_str = "V3 (XOR)"
        elif version == 1:
            # V4-V1 版本
            decrypted_data = WeChatImageDecryptor.decrypt_dat_v4(
                input_path, xor_key, aes_key
            )
            version_str = "V4-V1 (AES+XOR)"
        elif version == 2:
            # V4-V2 版本
            decrypted_data = WeChatImageDecryptor.decrypt_dat_v4(
                input_path, xor_key, aes_key
            )
            version_str = "V4-V2 (AES+XOR)"
        else:
            raise ImageDecryptError(f"未知版本: {version}")

        # 写入输出文件
        with open(output_path, 'wb') as f:
            f.write(decrypted_data)

        return version_str

    @staticmethod
    def detect_xor_key(file_path: str, known_headers: list = None) -> Optional[int]:
        """
        尝试检测 XOR 密钥（针对 V3 版本）

        通过尝试常见的图片文件头来检测 XOR 密钥

        Args:
            file_path: 文件路径
            known_headers: 已知的文件头列表，默认为常见图片格式

        Returns:
            检测到的 XOR 密钥，未检测到返回 None
        """
        if known_headers is None:
            # 常见图片格式的文件头
            known_headers = [
                b'\xFF\xD8\xFF',      # JPEG
                b'\x89\x50\x4E\x47',  # PNG
                b'\x47\x49\x46\x38',  # GIF
                b'\x42\x4D',          # BMP
                b'\x52\x49\x46\x46',  # WEBP (RIFF)
            ]

        try:
            with open(file_path, 'rb') as f:
                first_bytes = f.read(4)

            if len(first_bytes) < 2:
                return None

            # 尝试所有可能的 XOR 密钥
            for xor_key in range(256):
                decrypted_first = bytes(b ^ xor_key for b in first_bytes)

                # 检查是否匹配已知文件头
                for header in known_headers:
                    if decrypted_first.startswith(header):
                        return xor_key

            return None

        except Exception:
            return None


def main():
    """命令行测试"""
    import sys

    if len(sys.argv) < 4:
        print("用法: python image_decrypt.py <输入文件> <输出文件> <XOR密钥> [AES密钥]")
        print()
        print("参数:")
        print("  输入文件: .dat 文件路径")
        print("  输出文件: 解密后的图片文件路径")
        print("  XOR密钥: 0-255 的整数")
        print("  AES密钥: (可选) 16 字符的 ASCII 字符串，默认为 'cfcd208495d565ef'")
        print()
        print("示例:")
        print("  python image_decrypt.py image.dat image.jpg 123")
        print("  python image_decrypt.py image.dat image.jpg 123 customaeskey123")
        print()
        print("自动检测 XOR 密钥:")
        print("  python image_decrypt.py --detect <输入文件>")
        sys.exit(1)

    # 自动检测模式
    if sys.argv[1] == '--detect':
        if len(sys.argv) < 3:
            print("错误: 请提供文件路径")
            sys.exit(1)

        input_path = sys.argv[2]
        print(f"正在检测文件: {input_path}")
        print("-" * 60)

        xor_key = WeChatImageDecryptor.detect_xor_key(input_path)
        if xor_key is not None:
            print(f"✓ 检测到 XOR 密钥: {xor_key}")
            version = WeChatImageDecryptor.get_dat_version(input_path)
            print(f"文件版本: {['V3', 'V4-V1', 'V4-V2'][version]}")
        else:
            print("❌ 未检测到 XOR 密钥")
        sys.exit(0)

    # 解密模式
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    xor_key = int(sys.argv[3])

    aes_key = None
    if len(sys.argv) > 4:
        aes_key_str = sys.argv[4]
        if len(aes_key_str) != 16:
            print(f"错误: AES 密钥必须是 16 个字符，实际: {len(aes_key_str)}")
            sys.exit(1)
        aes_key = aes_key_str.encode('ascii')

    print("=" * 60)
    print("微信图片解密")
    print("=" * 60)
    print(f"输入文件: {input_path}")
    print(f"输出文件: {output_path}")
    print(f"XOR 密钥: {xor_key}")
    if aes_key:
        print(f"AES 密钥: {aes_key.decode('ascii')}")
    print()

    try:
        version_str = WeChatImageDecryptor.auto_decrypt_dat(
            input_path, output_path, xor_key, aes_key
        )
        print(f"✓ 解密成功！")
        print(f"文件版本: {version_str}")
        print(f"输出文件: {output_path}")
    except Exception as e:
        print(f"❌ 解密失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
