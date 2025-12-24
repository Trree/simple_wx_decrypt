"""
微信数据库解密核心模块
完美复刻 Go 版本的解密算法
支持 Windows V4 版本的微信数据库
"""

import struct
import hmac
import hashlib
from typing import Tuple, Optional, Callable
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


# 常量定义（与 Go 版本保持一致）
KEY_SIZE = 32           # 密钥大小：32 字节（256 位）
SALT_SIZE = 16          # 盐值大小：16 字节
IV_SIZE = 16            # IV 大小：16 字节
PAGE_SIZE = 4096        # 页面大小：4096 字节
HMAC_SHA512_SIZE = 64   # HMAC-SHA512 大小：64 字节
RESERVE = 80            # 保留区大小：80 字节
SQLITE_HEADER = b'SQLite format 3\x00'


class DecryptError(Exception):
    """解密错误基类"""
    pass


class InvalidKeyError(DecryptError):
    """密钥错误"""
    pass


class HMACVerificationError(DecryptError):
    """HMAC 验证失败"""
    pass


class WeChatDBDecryptor:
    """
    微信数据库解密器 (Windows V4)

    完美复刻 go_decrypt/internal/decrypt/windows/v4.go 的实现
    """

    def __init__(self, iter_count: int = 256000):
        """
        初始化解密器

        Args:
            iter_count: PBKDF2 迭代次数，默认 256000（Windows V4）
        """
        self.iter_count = iter_count
        self.page_size = PAGE_SIZE
        self.reserve = RESERVE
        self.hmac_size = HMAC_SHA512_SIZE
        self.backend = default_backend()

    def _derive_keys(self, key: bytes, salt: bytes) -> Tuple[bytes, bytes]:
        """
        派生加密密钥和 MAC 密钥

        对应 Go 代码：go_decrypt/internal/decrypt/windows/v4.go:54-64

        Args:
            key: 用户提供的原始密钥（32 字节）
            salt: 从数据库第一页提取的盐值（16 字节）

        Returns:
            (enc_key, mac_key) 元组
        """
        # 步骤 1：使用 PBKDF2-SHA512 派生加密密钥
        kdf_enc = PBKDF2HMAC(
            algorithm=hashes.SHA512(),
            length=KEY_SIZE,
            salt=salt,
            iterations=self.iter_count,
            backend=self.backend
        )
        enc_key = kdf_enc.derive(key)

        # 步骤 2：生成 MAC 盐值（salt XOR 0x3a）
        # 对应 Go 代码：common.XorBytes(salt, 0x3a)
        mac_salt = bytes(b ^ 0x3a for b in salt)

        # 步骤 3：使用加密密钥和 MAC 盐值派生 MAC 密钥
        # 注意：这里使用 enc_key 作为输入，迭代次数仅为 2
        kdf_mac = PBKDF2HMAC(
            algorithm=hashes.SHA512(),
            length=KEY_SIZE,
            salt=mac_salt,
            iterations=2,
            backend=self.backend
        )
        mac_key = kdf_mac.derive(enc_key)

        return enc_key, mac_key

    def _verify_page_hmac(
        self,
        page_buf: bytes,
        mac_key: bytes,
        page_num: int
    ) -> bool:
        """
        验证页面的 HMAC

        对应 Go 代码：go_decrypt/internal/decrypt/common/common.go:100-120

        Args:
            page_buf: 页面缓冲区（4096 字节）
            mac_key: MAC 密钥
            page_num: 页面号（从 0 开始）

        Returns:
            验证通过返回 True，否则返回 False
        """
        # 第一页需要跳过 salt（16 字节）
        offset = SALT_SIZE if page_num == 0 else 0

        # 创建 HMAC 对象
        h = hmac.new(mac_key, digestmod=hashlib.sha512)

        # 计算 HMAC 的数据范围：从 offset 到 (PAGE_SIZE - RESERVE + IV_SIZE)
        data_end = self.page_size - self.reserve + IV_SIZE
        h.update(page_buf[offset:data_end])

        # 添加页面号（Little-endian，4 字节）
        # 对应 Go 代码：binary.LittleEndian.PutUint32(pageNoBytes, uint32(pageNum+1))
        page_no_bytes = struct.pack('<I', page_num + 1)
        h.update(page_no_bytes)

        # 计算 HMAC
        calculated_hmac = h.digest()

        # 提取存储的 HMAC
        hmac_offset = self.page_size - self.reserve + IV_SIZE
        stored_hmac = page_buf[hmac_offset:hmac_offset + self.hmac_size]

        # 常量时间比较，防止时序攻击
        return hmac.compare_digest(calculated_hmac, stored_hmac)

    def _decrypt_page(
        self,
        page_buf: bytes,
        enc_key: bytes,
        mac_key: bytes,
        page_num: int
    ) -> bytes:
        """
        解密单个页面

        对应 Go 代码：go_decrypt/internal/decrypt/common/common.go:100-138

        Args:
            page_buf: 页面缓冲区（4096 字节）
            enc_key: 加密密钥
            mac_key: MAC 密钥
            page_num: 页面号（从 0 开始）

        Returns:
            解密后的页面数据

        Raises:
            HMACVerificationError: HMAC 验证失败
        """
        # 第一页需要跳过 salt（16 字节）
        offset = SALT_SIZE if page_num == 0 else 0

        # 步骤 1：验证 HMAC
        if not self._verify_page_hmac(page_buf, mac_key, page_num):
            raise HMACVerificationError(f"页面 {page_num} 的 HMAC 验证失败")

        # 步骤 2：提取 IV（16 字节）
        # IV 位于 (PAGE_SIZE - RESERVE) 到 (PAGE_SIZE - RESERVE + IV_SIZE)
        iv_offset = self.page_size - self.reserve
        iv = page_buf[iv_offset:iv_offset + IV_SIZE]

        # 步骤 3：提取需要解密的数据
        encrypted_data = page_buf[offset:iv_offset]

        # 步骤 4：AES-256-CBC 解密
        cipher = Cipher(
            algorithms.AES(enc_key),
            modes.CBC(iv),
            backend=self.backend
        )
        decryptor = cipher.decryptor()
        decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()

        # 步骤 5：拼接结果
        # 解密数据 + 尾部未加密部分（IV + HMAC + 填充）
        return decrypted_data + page_buf[iv_offset:self.page_size]

    def validate_key(self, db_path: str, hex_key: str) -> bool:
        """
        验证密钥是否正确

        对应 Go 代码：go_decrypt/internal/decrypt/windows/v4.go:66-74

        Args:
            db_path: 数据库文件路径
            hex_key: 十六进制格式的密钥（64 个字符）

        Returns:
            密钥正确返回 True，否则返回 False
        """
        try:
            # 解码十六进制密钥
            key = bytes.fromhex(hex_key)
            if len(key) != KEY_SIZE:
                return False

            # 读取第一页
            with open(db_path, 'rb') as f:
                first_page = f.read(self.page_size)

            if len(first_page) < self.page_size:
                return False

            # 提取盐值
            salt = first_page[:SALT_SIZE]

            # 派生密钥
            enc_key, mac_key = self._derive_keys(key, salt)

            # 验证第一页的 HMAC
            return self._verify_page_hmac(first_page, mac_key, 0)

        except Exception:
            return False

    def decrypt_database(
        self,
        input_path: str,
        output_path: str,
        hex_key: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> None:
        """
        解密整个数据库

        对应 Go 代码：go_decrypt/internal/decrypt/windows/v4.go:76-167

        Args:
            input_path: 输入的加密数据库路径
            output_path: 输出的解密数据库路径
            hex_key: 十六进制格式的密钥（64 个字符）
            progress_callback: 进度回调函数 callback(current, total)

        Raises:
            InvalidKeyError: 密钥错误
            DecryptError: 解密过程中的其他错误
        """
        # 步骤 1：解码十六进制密钥
        try:
            key = bytes.fromhex(hex_key)
        except ValueError as e:
            raise InvalidKeyError(f"无效的十六进制密钥: {e}")

        if len(key) != KEY_SIZE:
            raise InvalidKeyError(f"密钥长度错误：期望 {KEY_SIZE} 字节，实际 {len(key)} 字节")

        # 步骤 2：打开输入文件
        input_file = Path(input_path)
        if not input_file.exists():
            raise DecryptError(f"输入文件不存在: {input_path}")

        file_size = input_file.stat().st_size
        total_pages = file_size // self.page_size

        if total_pages == 0:
            raise DecryptError("文件太小，不是有效的数据库文件")

        # 步骤 3：读取第一页并验证密钥
        with open(input_path, 'rb') as f:
            first_page = f.read(self.page_size)

        if len(first_page) < self.page_size:
            raise DecryptError("无法读取完整的第一页")

        # 提取盐值
        salt = first_page[:SALT_SIZE]

        # 派生密钥
        enc_key, mac_key = self._derive_keys(key, salt)

        # 验证密钥
        if not self._verify_page_hmac(first_page, mac_key, 0):
            raise InvalidKeyError("密钥错误或数据库文件损坏")

        # 步骤 4：开始解密
        with open(input_path, 'rb') as f_in, open(output_path, 'wb') as f_out:
            for page_num in range(total_pages):
                # 读取页面
                page_buf = f_in.read(self.page_size)

                if len(page_buf) < self.page_size:
                    # 最后一页可能不完整，直接写入
                    if len(page_buf) > 0:
                        f_out.write(page_buf)
                    break

                try:
                    # 解密页面
                    decrypted_page = self._decrypt_page(
                        page_buf, enc_key, mac_key, page_num
                    )

                    # 第一页需要替换 SQLite 头部
                    if page_num == 0:
                        decrypted_page = SQLITE_HEADER + decrypted_page[len(SQLITE_HEADER):]

                    # 写入解密数据
                    f_out.write(decrypted_page)

                    # 进度回调
                    if progress_callback:
                        progress_callback(page_num + 1, total_pages)

                except HMACVerificationError as e:
                    raise DecryptError(f"解密失败: {e}")

        # 验证输出文件
        if not Path(output_path).exists():
            raise DecryptError("解密文件创建失败")

    def get_database_info(self, db_path: str) -> dict:
        """
        获取数据库信息（不需要密钥）

        Args:
            db_path: 数据库文件路径

        Returns:
            包含数据库信息的字典
        """
        db_file = Path(db_path)
        if not db_file.exists():
            raise DecryptError(f"文件不存在: {db_path}")

        file_size = db_file.stat().st_size
        total_pages = file_size // self.page_size

        with open(db_path, 'rb') as f:
            first_page = f.read(self.page_size)

        salt = first_page[:SALT_SIZE] if len(first_page) >= SALT_SIZE else b''

        return {
            'file_path': str(db_file.absolute()),
            'file_size': file_size,
            'file_size_mb': round(file_size / (1024 * 1024), 2),
            'total_pages': total_pages,
            'page_size': self.page_size,
            'salt': salt.hex() if salt else None,
            'encrypted': len(first_page) >= len(SQLITE_HEADER) and
                        first_page[:len(SQLITE_HEADER)] != SQLITE_HEADER
        }


def main():
    """命令行测试"""
    import sys

    if len(sys.argv) < 4:
        print("用法: python decrypt_core.py <输入文件> <输出文件> <密钥>")
        print("示例: python decrypt_core.py MSG0.db MSG0_decrypted.db 0123...cdef")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    hex_key = sys.argv[3]

    # 创建解密器
    decryptor = WeChatDBDecryptor()

    # 显示数据库信息
    print("=" * 60)
    print("数据库信息:")
    print("=" * 60)
    info = decryptor.get_database_info(input_path)
    for key, value in info.items():
        print(f"  {key}: {value}")
    print()

    # 验证密钥
    print("验证密钥...", end=' ')
    if not decryptor.validate_key(input_path, hex_key):
        print("❌ 失败")
        print("错误: 密钥不正确或数据库文件损坏")
        sys.exit(1)
    print("✓ 通过")
    print()

    # 解密数据库
    print("开始解密...")
    print("-" * 60)

    def progress(current, total):
        percent = (current / total) * 100
        bar_length = 40
        filled = int(bar_length * current / total)
        bar = '█' * filled + '░' * (bar_length - filled)
        print(f"\r进度: [{bar}] {percent:.1f}% ({current}/{total})", end='')

    try:
        decryptor.decrypt_database(input_path, output_path, hex_key, progress)
        print("\n" + "-" * 60)
        print(f"✓ 解密成功！")
        print(f"输出文件: {output_path}")
    except Exception as e:
        print("\n" + "-" * 60)
        print(f"❌ 解密失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
