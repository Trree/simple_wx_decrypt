"""
使用示例 - 演示如何使用解密库
"""

from decrypt_core import WeChatDBDecryptor, InvalidKeyError
from image_decrypt import WeChatImageDecryptor


def example_decrypt_database():
    """示例：解密数据库"""
    print("=" * 70)
    print("示例 1: 解密微信数据库")
    print("=" * 70)

    # 创建解密器
    decryptor = WeChatDBDecryptor()

    # 设置参数（请替换为实际值）
    input_db = "MSG0.db"
    output_db = "MSG0_decrypted.db"
    hex_key = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

    # 获取数据库信息
    print("\n1. 获取数据库信息:")
    try:
        info = decryptor.get_database_info(input_db)
        print(f"   文件大小: {info['file_size_mb']} MB")
        print(f"   页面总数: {info['total_pages']:,}")
        print(f"   加密状态: {info['encrypted']}")
    except Exception as e:
        print(f"   错误: {e}")
        return

    # 验证密钥
    print("\n2. 验证密钥:")
    if decryptor.validate_key(input_db, hex_key):
        print("   ✓ 密钥正确")
    else:
        print("   ✗ 密钥错误")
        return

    # 解密数据库
    print("\n3. 解密数据库:")

    def progress(current, total):
        if current % 100 == 0 or current == total:
            percent = (current / total) * 100
            print(f"   进度: {percent:.1f}% ({current:,}/{total:,})")

    try:
        decryptor.decrypt_database(input_db, output_db, hex_key, progress)
        print(f"   ✓ 解密成功！输出: {output_db}")

        # 验证输出
        import sqlite3
        conn = sqlite3.connect(output_db)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"   数据库表: {', '.join(tables)}")
        conn.close()

    except InvalidKeyError as e:
        print(f"   ✗ 密钥错误: {e}")
    except Exception as e:
        print(f"   ✗ 解密失败: {e}")


def example_decrypt_image():
    """示例：解密图片"""
    print("\n" + "=" * 70)
    print("示例 2: 解密微信图片")
    print("=" * 70)

    # 设置参数（请替换为实际值）
    input_dat = "image.dat"
    output_jpg = "image.jpg"
    xor_key = 123

    # 检测版本
    print("\n1. 检测文件版本:")
    try:
        version = WeChatImageDecryptor.get_dat_version(input_dat)
        version_names = {0: "V3 (XOR)", 1: "V4-V1 (AES+XOR)", 2: "V4-V2 (AES+XOR)"}
        print(f"   版本: {version_names.get(version, '未知')}")
    except Exception as e:
        print(f"   错误: {e}")
        return

    # 尝试自动检测 XOR 密钥
    print("\n2. 自动检测 XOR 密钥:")
    detected_key = WeChatImageDecryptor.detect_xor_key(input_dat)
    if detected_key is not None:
        print(f"   ✓ 检测到密钥: {detected_key}")
        xor_key = detected_key
    else:
        print(f"   使用手动指定的密钥: {xor_key}")

    # 解密图片
    print("\n3. 解密图片:")
    try:
        version_str = WeChatImageDecryptor.auto_decrypt_dat(
            input_dat, output_jpg, xor_key
        )
        print(f"   ✓ 解密成功！")
        print(f"   版本: {version_str}")
        print(f"   输出: {output_jpg}")
    except Exception as e:
        print(f"   ✗ 解密失败: {e}")


def example_batch_decrypt_images():
    """示例：批量解密图片"""
    print("\n" + "=" * 70)
    print("示例 3: 批量解密图片")
    print("=" * 70)

    import os
    from pathlib import Path

    # 设置目录（请替换为实际值）
    input_dir = "encrypted_images"
    output_dir = "decrypted_images"
    xor_key = 123

    # 创建输出目录
    Path(output_dir).mkdir(exist_ok=True)

    # 查找所有 .dat 文件
    dat_files = list(Path(input_dir).glob("*.dat"))
    print(f"\n找到 {len(dat_files)} 个 .dat 文件")

    if not dat_files:
        print("提示: 请将加密图片放到 encrypted_images 目录下")
        return

    # 批量解密
    success_count = 0
    for i, dat_file in enumerate(dat_files, 1):
        output_file = Path(output_dir) / f"{dat_file.stem}.jpg"

        print(f"\n[{i}/{len(dat_files)}] 处理: {dat_file.name}")

        try:
            # 尝试自动检测 XOR 密钥
            detected_key = WeChatImageDecryptor.detect_xor_key(str(dat_file))
            current_key = detected_key if detected_key is not None else xor_key

            # 解密
            WeChatImageDecryptor.auto_decrypt_dat(
                str(dat_file), str(output_file), current_key
            )

            success_count += 1
            print(f"   ✓ 成功 (XOR密钥: {current_key})")

        except Exception as e:
            print(f"   ✗ 失败: {e}")

    print(f"\n完成！成功: {success_count}/{len(dat_files)}")


def example_integrate_decrypt():
    """示例：完整的解密流程"""
    print("\n" + "=" * 70)
    print("示例 4: 完整解密流程")
    print("=" * 70)

    # 步骤 1: 解密数据库
    print("\n步骤 1: 解密数据库")
    print("-" * 70)

    db_decryptor = WeChatDBDecryptor()

    input_db = "MSG0.db"
    output_db = "MSG0_decrypted.db"
    hex_key = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

    try:
        # 验证密钥
        if not db_decryptor.validate_key(input_db, hex_key):
            print("错误: 数据库密钥不正确")
            return

        # 解密
        db_decryptor.decrypt_database(
            input_db, output_db, hex_key,
            lambda c, t: print(f"数据库解密进度: {c}/{t}") if c % 100 == 0 else None
        )
        print("✓ 数据库解密完成")

    except Exception as e:
        print(f"✗ 数据库解密失败: {e}")
        return

    # 步骤 2: 查询数据库获取图片路径
    print("\n步骤 2: 从数据库查询图片路径")
    print("-" * 70)

    import sqlite3

    try:
        conn = sqlite3.connect(output_db)
        cursor = conn.execute("""
            SELECT ImgPath FROM MSG
            WHERE Type=3 AND ImgPath IS NOT NULL
            LIMIT 10
        """)

        image_paths = [row[0] for row in cursor.fetchall()]
        conn.close()

        print(f"找到 {len(image_paths)} 张图片")

    except Exception as e:
        print(f"警告: 查询图片失败: {e}")
        image_paths = []

    # 步骤 3: 解密图片
    if image_paths:
        print("\n步骤 3: 解密图片")
        print("-" * 70)

        xor_key = 123  # 替换为实际的 XOR 密钥

        for i, img_path in enumerate(image_paths[:3], 1):  # 仅处理前 3 张
            output_path = f"decrypted_image_{i}.jpg"

            try:
                WeChatImageDecryptor.auto_decrypt_dat(img_path, output_path, xor_key)
                print(f"✓ 图片 {i} 解密成功: {output_path}")
            except Exception as e:
                print(f"✗ 图片 {i} 解密失败: {e}")

    print("\n" + "=" * 70)
    print("完整流程结束")
    print("=" * 70)


def main():
    """主函数"""
    print("\n微信数据解密工具 - 使用示例\n")

    # 显示菜单
    examples = [
        ("解密数据库", example_decrypt_database),
        ("解密图片", example_decrypt_image),
        ("批量解密图片", example_batch_decrypt_images),
        ("完整解密流程", example_integrate_decrypt),
    ]

    print("可用示例:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")

    print("\n注意: 请先修改示例代码中的文件路径和密钥！")
    print("\n提示: 直接运行各个示例函数查看效果")
    print("      例如: example_decrypt_database()")


if __name__ == '__main__':
    main()
