#!/usr/bin/env python3
"""
微信数据解密工具
统一命令行接口，支持数据库和图片解密
"""

import sys
import argparse
from pathlib import Path
from typing import Optional

try:
    from decrypt_core import WeChatDBDecryptor, DecryptError, InvalidKeyError
    from image_decrypt import WeChatImageDecryptor, ImageDecryptError
except ImportError:
    print("错误: 无法导入解密模块，请确保在正确的目录下运行")
    print("或使用: python -m wechat_decrypt")
    sys.exit(1)


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def decrypt_database_cmd(args):
    """解密数据库命令"""
    print("=" * 70)
    print("微信数据库解密")
    print("=" * 70)

    decryptor = WeChatDBDecryptor()

    # 显示数据库信息
    try:
        info = decryptor.get_database_info(args.input)
        print("\n数据库信息:")
        print(f"  文件路径: {info['file_path']}")
        print(f"  文件大小: {format_file_size(info['file_size'])} ({info['file_size']:,} 字节)")
        print(f"  页面总数: {info['total_pages']:,}")
        print(f"  页面大小: {info['page_size']} 字节")
        if info['salt']:
            print(f"  盐值(Salt): {info['salt'][:32]}...")
        print(f"  加密状态: {'是' if info['encrypted'] else '否'}")
        print()
    except Exception as e:
        print(f"警告: 无法读取数据库信息: {e}\n")

    # 验证密钥
    if not args.skip_validation:
        print("正在验证密钥...", end=' ', flush=True)
        if not decryptor.validate_key(args.input, args.key):
            print("❌ 失败")
            print("\n错误: 密钥不正确或数据库文件损坏")
            print("提示: 使用 --skip-validation 跳过验证（不推荐）")
            return 1
        print("✓ 通过")
        print()

    # 解密数据库
    print("开始解密...")
    print("-" * 70)

    def progress_callback(current: int, total: int):
        percent = (current / total) * 100
        bar_length = 50
        filled = int(bar_length * current / total)
        bar = '█' * filled + '░' * (bar_length - filled)
        print(f"\r进度: [{bar}] {percent:.1f}% ({current:,}/{total:,})", end='', flush=True)

    try:
        decryptor.decrypt_database(
            args.input,
            args.output,
            args.key,
            progress_callback if not args.quiet else None
        )

        print("\n" + "-" * 70)
        print("✓ 解密成功！")
        print(f"\n输出文件: {Path(args.output).absolute()}")

        # 显示输出文件大小
        output_size = Path(args.output).stat().st_size
        print(f"文件大小: {format_file_size(output_size)}")

        return 0

    except InvalidKeyError as e:
        print("\n" + "-" * 70)
        print(f"❌ 密钥错误: {e}")
        return 1
    except DecryptError as e:
        print("\n" + "-" * 70)
        print(f"❌ 解密失败: {e}")
        return 1
    except Exception as e:
        print("\n" + "-" * 70)
        print(f"❌ 未知错误: {e}")
        return 1


def decrypt_image_cmd(args):
    """解密图片命令"""
    print("=" * 70)
    print("微信图片解密")
    print("=" * 70)

    # 显示文件信息
    input_path = Path(args.input)
    file_size = input_path.stat().st_size

    print("\n文件信息:")
    print(f"  输入文件: {input_path.absolute()}")
    print(f"  文件大小: {format_file_size(file_size)}")

    # 检测版本
    try:
        version = WeChatImageDecryptor.get_dat_version(args.input)
        version_names = {0: "V3 (简单 XOR)", 1: "V4-V1 (AES+XOR)", 2: "V4-V2 (AES+XOR)"}
        print(f"  文件版本: {version_names.get(version, '未知')}")
    except Exception as e:
        print(f"  文件版本: 检测失败 ({e})")

    print(f"  XOR 密钥: {args.xor_key}")
    if args.aes_key:
        print(f"  AES 密钥: {args.aes_key}")
    print()

    # 解密
    print("开始解密...")

    try:
        aes_key = args.aes_key.encode('ascii') if args.aes_key else None

        version_str = WeChatImageDecryptor.auto_decrypt_dat(
            args.input,
            args.output,
            args.xor_key,
            aes_key
        )

        print(f"✓ 解密成功！ (版本: {version_str})")
        print(f"\n输出文件: {Path(args.output).absolute()}")

        # 显示输出文件大小
        output_size = Path(args.output).stat().st_size
        print(f"文件大小: {format_file_size(output_size)}")

        return 0

    except ImageDecryptError as e:
        print(f"❌ 解密失败: {e}")
        return 1
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return 1


def detect_xor_key_cmd(args):
    """检测 XOR 密钥命令"""
    print("=" * 70)
    print("XOR 密钥检测")
    print("=" * 70)

    input_path = Path(args.input)
    print(f"\n正在分析文件: {input_path.absolute()}")
    print("-" * 70)

    try:
        # 检测版本
        version = WeChatImageDecryptor.get_dat_version(args.input)
        version_names = {0: "V3 (简单 XOR)", 1: "V4-V1 (AES+XOR)", 2: "V4-V2 (AES+XOR)"}
        print(f"文件版本: {version_names.get(version, '未知')}")

        # 检测 XOR 密钥
        print("正在检测 XOR 密钥...", end=' ', flush=True)
        xor_key = WeChatImageDecryptor.detect_xor_key(args.input)

        if xor_key is not None:
            print(f"✓ 检测成功")
            print(f"\nXOR 密钥: {xor_key} (0x{xor_key:02X})")
            print(f"\n使用方法:")
            print(f"  python wechat_decrypt.py image -i {args.input} -o output.jpg -x {xor_key}")
        else:
            print("❌ 未检测到密钥")
            print("\n提示:")
            print("  - 确保文件是有效的微信加密图片")
            print("  - V4 版本可能需要手动提供 XOR 密钥")

        return 0

    except Exception as e:
        print(f"❌ 检测失败: {e}")
        return 1


def validate_key_cmd(args):
    """验证密钥命令"""
    print("=" * 70)
    print("密钥验证")
    print("=" * 70)

    decryptor = WeChatDBDecryptor()

    print(f"\n数据库文件: {Path(args.input).absolute()}")
    print(f"密钥: {args.key[:16]}...{args.key[-16:]}")
    print()

    print("正在验证...", end=' ', flush=True)

    is_valid = decryptor.validate_key(args.input, args.key)

    if is_valid:
        print("✓ 密钥正确")
        print("\n✓ 此密钥可用于解密该数据库")
        return 0
    else:
        print("❌ 密钥错误")
        print("\n✗ 密钥不正确或数据库文件损坏")
        print("\n提示:")
        print("  - 确保密钥是 64 位十六进制字符串")
        print("  - 确保数据库文件未损坏")
        return 1


def info_cmd(args):
    """显示文件信息命令"""
    print("=" * 70)
    print("文件信息")
    print("=" * 70)

    file_path = Path(args.input)
    if not file_path.exists():
        print(f"\n错误: 文件不存在: {args.input}")
        return 1

    file_size = file_path.stat().st_size
    print(f"\n文件路径: {file_path.absolute()}")
    print(f"文件大小: {format_file_size(file_size)} ({file_size:,} 字节)")

    # 尝试作为数据库读取
    try:
        decryptor = WeChatDBDecryptor()
        info = decryptor.get_database_info(args.input)

        print(f"\n数据库信息:")
        print(f"  页面总数: {info['total_pages']:,}")
        print(f"  页面大小: {info['page_size']} 字节")
        if info['salt']:
            print(f"  盐值: {info['salt']}")
        print(f"  加密状态: {'是' if info['encrypted'] else '否'}")
    except:
        pass

    # 尝试作为图片读取
    try:
        version = WeChatImageDecryptor.get_dat_version(args.input)
        version_names = {0: "V3 (简单 XOR)", 1: "V4-V1 (AES+XOR)", 2: "V4-V2 (AES+XOR)"}

        print(f"\n图片信息:")
        print(f"  文件版本: {version_names.get(version, '未知')}")

        # 尝试检测 XOR 密钥
        xor_key = WeChatImageDecryptor.detect_xor_key(args.input)
        if xor_key is not None:
            print(f"  检测到 XOR 密钥: {xor_key} (0x{xor_key:02X})")
    except:
        pass

    return 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='微信数据解密工具 - 支持数据库和图片解密',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 解密数据库
  %(prog)s db -i MSG0.db -o MSG0_decrypted.db -k 0123456789abcdef...

  # 验证密钥
  %(prog)s validate -i MSG0.db -k 0123456789abcdef...

  # 解密图片
  %(prog)s image -i image.dat -o image.jpg -x 123

  # 检测图片 XOR 密钥
  %(prog)s detect -i image.dat

  # 显示文件信息
  %(prog)s info -i MSG0.db
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='命令')

    # 数据库解密命令
    db_parser = subparsers.add_parser('db', help='解密数据库')
    db_parser.add_argument('-i', '--input', required=True, help='输入数据库文件')
    db_parser.add_argument('-o', '--output', required=True, help='输出数据库文件')
    db_parser.add_argument('-k', '--key', required=True, help='64 位十六进制密钥')
    db_parser.add_argument('--skip-validation', action='store_true', help='跳过密钥验证')
    db_parser.add_argument('-q', '--quiet', action='store_true', help='安静模式（不显示进度）')

    # 密钥验证命令
    validate_parser = subparsers.add_parser('validate', help='验证密钥')
    validate_parser.add_argument('-i', '--input', required=True, help='数据库文件')
    validate_parser.add_argument('-k', '--key', required=True, help='64 位十六进制密钥')

    # 图片解密命令
    image_parser = subparsers.add_parser('image', help='解密图片')
    image_parser.add_argument('-i', '--input', required=True, help='输入 .dat 文件')
    image_parser.add_argument('-o', '--output', required=True, help='输出图片文件')
    image_parser.add_argument('-x', '--xor-key', type=int, required=True, help='XOR 密钥 (0-255)')
    image_parser.add_argument('-a', '--aes-key', help='AES 密钥 (16 字符，可选)')

    # XOR 密钥检测命令
    detect_parser = subparsers.add_parser('detect', help='检测图片 XOR 密钥')
    detect_parser.add_argument('-i', '--input', required=True, help='输入 .dat 文件')

    # 文件信息命令
    info_parser = subparsers.add_parser('info', help='显示文件信息')
    info_parser.add_argument('-i', '--input', required=True, help='文件路径')

    # 解析参数
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # 执行命令
    try:
        if args.command == 'db':
            return decrypt_database_cmd(args)
        elif args.command == 'validate':
            return validate_key_cmd(args)
        elif args.command == 'image':
            return decrypt_image_cmd(args)
        elif args.command == 'detect':
            return detect_xor_key_cmd(args)
        elif args.command == 'info':
            return info_cmd(args)
        else:
            parser.print_help()
            return 1
    except KeyboardInterrupt:
        print("\n\n操作已取消")
        return 130
    except Exception as e:
        print(f"\n未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
