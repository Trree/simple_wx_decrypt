#!/usr/bin/env python3
"""
批量数据库解密模块
按照 EchoTrace 思路：扫描目录，保持结构，批量解密
"""

import os
import shutil
from pathlib import Path
from typing import List, Tuple, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime

from decrypt_core import WeChatDBDecryptor, DecryptError, InvalidKeyError


@dataclass
class DatabaseFile:
    """数据库文件信息"""
    source_path: Path          # 源文件绝对路径
    relative_path: Path        # 相对于根目录的路径
    file_size: int            # 文件大小（字节）
    filename: str             # 文件名

    def __str__(self):
        return f"{self.relative_path} ({self.file_size:,} bytes)"


@dataclass
class DecryptResult:
    """解密结果"""
    db_file: DatabaseFile
    success: bool
    output_path: Optional[Path]
    error: Optional[str]
    duration: float  # 秒


class BatchDecryptor:
    """
    批量解密器

    功能：
    1. 扫描目录下所有 .db 文件
    2. 保持原有目录结构
    3. 批量解密到输出目录
    """

    def __init__(self, key: str, skip_validation: bool = False):
        """
        初始化批量解密器

        Args:
            key: 64位十六进制密钥
            skip_validation: 是否跳过密钥验证
        """
        self.key = key
        self.skip_validation = skip_validation
        self.decryptor = WeChatDBDecryptor()

    def scan_databases(self, root_dir: str) -> List[DatabaseFile]:
        """
        扫描目录下的所有数据库文件

        Args:
            root_dir: 根目录路径

        Returns:
            数据库文件列表
        """
        root_path = Path(root_dir).resolve()
        if not root_path.exists():
            raise FileNotFoundError(f"目录不存在: {root_dir}")

        if not root_path.is_dir():
            raise NotADirectoryError(f"不是目录: {root_dir}")

        db_files = []

        # 递归搜索所有 .db 文件
        for db_path in root_path.rglob('*.db'):
            if db_path.is_file():
                try:
                    relative_path = db_path.relative_to(root_path)
                    file_size = db_path.stat().st_size

                    db_file = DatabaseFile(
                        source_path=db_path,
                        relative_path=relative_path,
                        file_size=file_size,
                        filename=db_path.name
                    )
                    db_files.append(db_file)
                except Exception as e:
                    print(f"警告: 无法读取文件 {db_path}: {e}")

        # 按相对路径排序
        db_files.sort(key=lambda x: str(x.relative_path))

        return db_files

    def decrypt_single(
        self,
        db_file: DatabaseFile,
        output_root: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> DecryptResult:
        """
        解密单个数据库文件

        Args:
            db_file: 数据库文件信息
            output_root: 输出根目录
            progress_callback: 进度回调

        Returns:
            解密结果
        """
        start_time = datetime.now()

        try:
            # 构建输出路径（保持相对路径结构）
            output_path = output_root / db_file.relative_path

            # 创建输出目录
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 验证密钥（如果需要）
            if not self.skip_validation:
                if not self.decryptor.validate_key(str(db_file.source_path), self.key):
                    raise InvalidKeyError("密钥验证失败")

            # 解密数据库
            self.decryptor.decrypt_database(
                str(db_file.source_path),
                str(output_path),
                self.key,
                progress_callback
            )

            duration = (datetime.now() - start_time).total_seconds()

            return DecryptResult(
                db_file=db_file,
                success=True,
                output_path=output_path,
                error=None,
                duration=duration
            )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return DecryptResult(
                db_file=db_file,
                success=False,
                output_path=None,
                error=str(e),
                duration=duration
            )

    def decrypt_batch(
        self,
        root_dir: str,
        output_dir: str,
        max_workers: int = 4,
        progress_callback: Optional[Callable[[str, int, int, int], None]] = None
    ) -> Tuple[List[DecryptResult], List[DecryptResult]]:
        """
        批量解密目录下的所有数据库

        Args:
            root_dir: 输入根目录
            output_dir: 输出根目录
            max_workers: 最大并行数（默认4）
            progress_callback: 进度回调 (filename, current, total, total_files)

        Returns:
            (成功列表, 失败列表)
        """
        # 扫描数据库文件
        db_files = self.scan_databases(root_dir)

        if not db_files:
            raise ValueError(f"未找到任何 .db 文件: {root_dir}")

        output_root = Path(output_dir).resolve()
        output_root.mkdir(parents=True, exist_ok=True)

        success_results = []
        failed_results = []

        # 并行解密
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_db = {}
            for db_file in db_files:
                future = executor.submit(
                    self.decrypt_single,
                    db_file,
                    output_root,
                    None  # 单文件进度回调在批量模式下禁用
                )
                future_to_db[future] = db_file

            # 收集结果
            completed_count = 0
            for future in as_completed(future_to_db):
                result = future.result()
                completed_count += 1

                if result.success:
                    success_results.append(result)
                else:
                    failed_results.append(result)

                # 调用进度回调
                if progress_callback:
                    progress_callback(
                        result.db_file.filename,
                        completed_count,
                        len(db_files),
                        len(db_files)
                    )

        return success_results, failed_results

    def decrypt_batch_sequential(
        self,
        root_dir: str,
        output_dir: str,
        file_progress_callback: Optional[Callable[[int, int], None]] = None,
        overall_progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> Tuple[List[DecryptResult], List[DecryptResult]]:
        """
        顺序批量解密（显示详细进度）

        Args:
            root_dir: 输入根目录
            output_dir: 输出根目录
            file_progress_callback: 单文件进度回调 (current_page, total_pages)
            overall_progress_callback: 整体进度回调 (filename, current_file, total_files)

        Returns:
            (成功列表, 失败列表)
        """
        # 扫描数据库文件
        db_files = self.scan_databases(root_dir)

        if not db_files:
            raise ValueError(f"未找到任何 .db 文件: {root_dir}")

        output_root = Path(output_dir).resolve()
        output_root.mkdir(parents=True, exist_ok=True)

        success_results = []
        failed_results = []

        # 顺序解密
        for idx, db_file in enumerate(db_files, 1):
            # 整体进度回调
            if overall_progress_callback:
                overall_progress_callback(db_file.filename, idx, len(db_files))

            # 解密单个文件
            result = self.decrypt_single(
                db_file,
                output_root,
                file_progress_callback
            )

            if result.success:
                success_results.append(result)
            else:
                failed_results.append(result)

        return success_results, failed_results


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def format_duration(seconds: float) -> str:
    """格式化时长"""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        return f"{seconds // 60:.0f}分{seconds % 60:.0f}秒"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours:.0f}小时{minutes:.0f}分"


def main():
    """命令行测试"""
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description='批量解密微信数据库',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 批量解密（保持目录结构）
  python batch_decrypt.py -i "C:/WeChat Files/wxid_xxx" -o "./decrypted" -k 0123...cdef

  # 并行解密（4线程）
  python batch_decrypt.py -i ./input -o ./output -k 0123...cdef --parallel 4

  # 跳过密钥验证
  python batch_decrypt.py -i ./input -o ./output -k 0123...cdef --skip-validation
        """
    )

    parser.add_argument('-i', '--input', required=True, help='输入根目录')
    parser.add_argument('-o', '--output', required=True, help='输出根目录')
    parser.add_argument('-k', '--key', required=True, help='64位十六进制密钥')
    parser.add_argument('--parallel', type=int, default=0, help='并行线程数（0=顺序，默认0）')
    parser.add_argument('--skip-validation', action='store_true', help='跳过密钥验证')
    parser.add_argument('--scan-only', action='store_true', help='仅扫描，不解密')

    args = parser.parse_args()

    print("=" * 70)
    print("微信数据库批量解密")
    print("=" * 70)
    print()

    # 创建批量解密器
    batch_decryptor = BatchDecryptor(args.key, args.skip_validation)

    # 扫描数据库
    print(f"正在扫描目录: {args.input}")
    print("-" * 70)

    try:
        db_files = batch_decryptor.scan_databases(args.input)
    except Exception as e:
        print(f"❌ 扫描失败: {e}")
        return 1

    if not db_files:
        print("未找到任何 .db 文件")
        return 1

    print(f"✓ 找到 {len(db_files)} 个数据库文件:\n")

    total_size = 0
    for idx, db_file in enumerate(db_files, 1):
        print(f"  {idx:3d}. {db_file.relative_path}")
        print(f"       大小: {format_size(db_file.file_size)}")
        total_size += db_file.file_size

    print()
    print(f"总大小: {format_size(total_size)}")
    print()

    if args.scan_only:
        print("仅扫描模式，退出")
        return 0

    # 开始解密
    print("=" * 70)
    print("开始批量解密")
    print("=" * 70)
    print(f"输出目录: {args.output}")
    print(f"并行数: {args.parallel if args.parallel > 0 else '顺序'}")
    print()

    start_time = datetime.now()

    try:
        if args.parallel > 0:
            # 并行解密
            def progress_callback(filename, current, total, total_files):
                percent = (current / total) * 100
                print(f"\r进度: [{current}/{total}] {percent:.1f}% | 当前: {filename[:40]:<40}", end='', flush=True)

            success_results, failed_results = batch_decryptor.decrypt_batch(
                args.input,
                args.output,
                max_workers=args.parallel,
                progress_callback=progress_callback
            )
        else:
            # 顺序解密
            def file_progress(current, total):
                percent = (current / total) * 100
                bar_length = 40
                filled = int(bar_length * current / total)
                bar = '█' * filled + '░' * (bar_length - filled)
                print(f"\r  [{bar}] {percent:.1f}%", end='', flush=True)

            def overall_progress(filename, current, total):
                print(f"\n[{current}/{total}] {filename}")

            success_results, failed_results = batch_decryptor.decrypt_batch_sequential(
                args.input,
                args.output,
                file_progress_callback=file_progress,
                overall_progress_callback=overall_progress
            )

        print("\n")
    except Exception as e:
        print(f"\n❌ 批量解密失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # 显示结果
    duration = (datetime.now() - start_time).total_seconds()

    print("=" * 70)
    print("解密完成")
    print("=" * 70)
    print()
    print(f"总耗时: {format_duration(duration)}")
    print(f"成功: {len(success_results)} 个")
    print(f"失败: {len(failed_results)} 个")
    print()

    if success_results:
        print("✓ 成功:")
        total_success_size = 0
        for result in success_results:
            print(f"  ✓ {result.db_file.relative_path}")
            print(f"    耗时: {result.duration:.1f}秒 | 输出: {result.output_path}")
            total_success_size += result.db_file.file_size
        print(f"  总大小: {format_size(total_success_size)}")
        print()

    if failed_results:
        print("✗ 失败:")
        for result in failed_results:
            print(f"  ✗ {result.db_file.relative_path}")
            print(f"    错误: {result.error}")
        print()

    return 0 if not failed_results else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
