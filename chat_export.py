"""
微信聊天记录导出模块
从解密后的数据库中读取聊天记录并导出为 Markdown 格式
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


class ChatExportError(Exception):
    """聊天记录导出错误"""
    pass


class WeChatChatExporter:
    """
    微信聊天记录导出器

    支持从解密后的 SQLite 数据库中提取聊天记录并导出为 Markdown 格式
    """

    def __init__(self, db_path: str):
        """
        初始化导出器

        Args:
            db_path: 解密后的数据库文件路径
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise ChatExportError(f"数据库文件不存在: {db_path}")

        self.conn = None

    def connect(self):
        """连接到数据库"""
        try:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            raise ChatExportError(f"无法连接到数据库: {e}")

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()

    def get_tables(self) -> List[str]:
        """
        获取数据库中的所有表

        Returns:
            表名列表
        """
        if not self.conn:
            raise ChatExportError("数据库未连接")

        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [row[0] for row in cursor.fetchall()]

    def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """
        获取表的结构信息

        Args:
            table_name: 表名

        Returns:
            表结构信息列表
        """
        if not self.conn:
            raise ChatExportError("数据库未连接")

        cursor = self.conn.execute(f"PRAGMA table_info({table_name})")
        columns = []
        for row in cursor.fetchall():
            columns.append({
                'cid': row[0],
                'name': row[1],
                'type': row[2],
                'notnull': row[3],
                'default': row[4],
                'pk': row[5]
            })
        return columns

    def get_table_count(self, table_name: str) -> int:
        """
        获取表的记录数

        Args:
            table_name: 表名

        Returns:
            记录数
        """
        if not self.conn:
            raise ChatExportError("数据库未连接")

        cursor = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}")
        return cursor.fetchone()[0]

    def query_messages(
        self,
        table_name: str = "MSG",
        limit: Optional[int] = None,
        offset: int = 0,
        where_clause: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        查询消息记录

        Args:
            table_name: 消息表名，默认为 "MSG"
            limit: 限制返回的记录数
            offset: 跳过的记录数
            where_clause: WHERE 子句（不包含 WHERE 关键字）

        Returns:
            消息记录列表
        """
        if not self.conn:
            raise ChatExportError("数据库未连接")

        # 检查表是否存在
        tables = self.get_tables()
        if table_name not in tables:
            raise ChatExportError(f"表不存在: {table_name}")

        # 构建查询语句
        query = f"SELECT * FROM {table_name}"
        if where_clause:
            query += f" WHERE {where_clause}"
        query += " ORDER BY CreateTime ASC" if "CreateTime" in [c['name'] for c in self.get_table_info(table_name)] else ""
        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"

        cursor = self.conn.execute(query)

        # 转换为字典列表
        messages = []
        for row in cursor.fetchall():
            message = dict(row)
            messages.append(message)

        return messages

    def _format_timestamp(self, timestamp: int) -> str:
        """
        格式化时间戳

        Args:
            timestamp: 时间戳（秒或毫秒）

        Returns:
            格式化的时间字符串
        """
        try:
            # 微信时间戳通常是秒，如果大于 10000000000 则是毫秒
            if timestamp > 10000000000:
                dt = datetime.fromtimestamp(timestamp / 1000)
            else:
                dt = datetime.fromtimestamp(timestamp)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return str(timestamp)

    def _format_message_type(self, msg_type: int) -> str:
        """
        格式化消息类型

        Args:
            msg_type: 消息类型代码

        Returns:
            消息类型描述
        """
        type_map = {
            1: "文本",
            3: "图片",
            34: "语音",
            42: "名片",
            43: "视频",
            47: "表情",
            48: "位置",
            49: "链接/文件",
            50: "语音通话",
            10000: "系统消息",
        }
        return type_map.get(msg_type, f"未知类型({msg_type})")

    def _format_message_content(self, message: Dict[str, Any]) -> str:
        """
        格式化消息内容

        Args:
            message: 消息字典

        Returns:
            格式化后的内容
        """
        # 尝试获取消息内容
        content = message.get('StrContent') or message.get('Content') or message.get('content') or ''
        msg_type = message.get('Type') or message.get('MsgType') or message.get('type') or 0

        # 根据消息类型格式化
        if msg_type == 1:  # 文本消息
            return content
        elif msg_type == 3:  # 图片
            return f"[图片] {content[:50]}..." if len(content) > 50 else f"[图片] {content}"
        elif msg_type == 34:  # 语音
            return "[语音消息]"
        elif msg_type == 43:  # 视频
            return "[视频消息]"
        elif msg_type == 47:  # 表情
            return "[表情]"
        elif msg_type == 48:  # 位置
            return f"[位置] {content[:30]}..." if len(content) > 30 else f"[位置] {content}"
        elif msg_type == 49:  # 链接/文件
            return f"[链接/文件] {content[:50]}..." if len(content) > 50 else f"[链接/文件] {content}"
        elif msg_type == 10000:  # 系统消息
            return f"**系统消息**: {content}"
        else:
            return content[:100] + "..." if len(content) > 100 else content

    def export_to_markdown(
        self,
        output_path: str,
        table_name: str = "MSG",
        limit: Optional[int] = None,
        title: str = "微信聊天记录",
        include_stats: bool = True
    ) -> None:
        """
        导出聊天记录到 Markdown 文件

        Args:
            output_path: 输出的 Markdown 文件路径
            table_name: 消息表名
            limit: 限制导出的消息数量（None 表示全部导出）
            title: Markdown 文档标题
            include_stats: 是否包含统计信息
        """
        if not self.conn:
            raise ChatExportError("数据库未连接")

        # 查询消息
        try:
            messages = self.query_messages(table_name, limit=limit)
        except ChatExportError as e:
            raise ChatExportError(f"查询消息失败: {e}")

        if not messages:
            raise ChatExportError(f"表 {table_name} 中没有找到消息记录")

        # 获取表信息
        columns = self.get_table_info(table_name)
        column_names = [c['name'] for c in columns]

        # 生成 Markdown 内容
        md_lines = []

        # 标题
        md_lines.append(f"# {title}\n")
        md_lines.append(f"> 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        md_lines.append(f"> 数据库: {self.db_path.name}\n")
        md_lines.append(f"> 消息表: {table_name}\n")

        # 统计信息
        if include_stats:
            total_count = self.get_table_count(table_name)
            md_lines.append(f"\n## 📊 统计信息\n")
            md_lines.append(f"- 总消息数: {total_count:,}\n")
            md_lines.append(f"- 导出消息数: {len(messages):,}\n")

            # 统计消息类型
            type_counts = {}
            for msg in messages:
                msg_type = msg.get('Type') or msg.get('MsgType') or msg.get('type') or 0
                type_name = self._format_message_type(msg_type)
                type_counts[type_name] = type_counts.get(type_name, 0) + 1

            md_lines.append(f"\n### 消息类型分布\n")
            for type_name, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
                md_lines.append(f"- {type_name}: {count:,}\n")

        # 消息列表
        md_lines.append(f"\n## 💬 聊天记录\n")
        md_lines.append(f"> 共 {len(messages)} 条消息\n\n")
        md_lines.append("---\n\n")

        # 遍历消息
        for i, msg in enumerate(messages, 1):
            # 提取关键字段
            msg_id = msg.get('MsgSvrID') or msg.get('MsgId') or msg.get('msgid') or i
            talker = msg.get('StrTalker') or msg.get('Talker') or msg.get('talker') or '未知'
            create_time = msg.get('CreateTime') or msg.get('createtime') or 0
            msg_type = msg.get('Type') or msg.get('MsgType') or msg.get('type') or 0
            is_sender = msg.get('IsSender') or msg.get('isSender') or msg.get('issender') or 0

            # 格式化时间
            time_str = self._format_timestamp(create_time)

            # 格式化消息类型
            type_str = self._format_message_type(msg_type)

            # 格式化内容
            content = self._format_message_content(msg)

            # 判断发送者
            sender_label = "我" if is_sender else talker

            # 写入消息
            md_lines.append(f"### 消息 #{i}\n\n")
            md_lines.append(f"- **时间**: {time_str}\n")
            md_lines.append(f"- **发送者**: {sender_label}\n")
            md_lines.append(f"- **类型**: {type_str}\n")
            md_lines.append(f"- **内容**:\n\n")

            # 内容使用引用格式
            content_lines = content.split('\n')
            for line in content_lines:
                md_lines.append(f"  > {line}\n")

            md_lines.append(f"\n---\n\n")

        # 写入文件
        output_file = Path(output_path)
        try:
            output_file.write_text('\n'.join(md_lines), encoding='utf-8')
        except Exception as e:
            raise ChatExportError(f"写入文件失败: {e}")

    def export_database_info(self, output_path: str) -> None:
        """
        导出数据库结构信息到 Markdown 文件

        Args:
            output_path: 输出的 Markdown 文件路径
        """
        if not self.conn:
            raise ChatExportError("数据库未连接")

        md_lines = []

        # 标题
        md_lines.append(f"# 微信数据库结构\n")
        md_lines.append(f"> 数据库: {self.db_path.name}\n")
        md_lines.append(f"> 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # 获取所有表
        tables = self.get_tables()
        md_lines.append(f"## 数据库表列表\n\n")
        md_lines.append(f"共 {len(tables)} 个表\n\n")

        # 遍历每个表
        for table in tables:
            md_lines.append(f"### 📋 {table}\n\n")

            # 获取记录数
            try:
                count = self.get_table_count(table)
                md_lines.append(f"**记录数**: {count:,}\n\n")
            except Exception as e:
                md_lines.append(f"**记录数**: 无法获取 ({e})\n\n")

            # 获取表结构
            try:
                columns = self.get_table_info(table)
                md_lines.append("**表结构**:\n\n")
                md_lines.append("| 列名 | 类型 | 非空 | 默认值 | 主键 |\n")
                md_lines.append("|------|------|------|--------|------|\n")

                for col in columns:
                    name = col['name']
                    type_ = col['type']
                    notnull = '✓' if col['notnull'] else ''
                    default = col['default'] if col['default'] else ''
                    pk = '✓' if col['pk'] else ''
                    md_lines.append(f"| {name} | {type_} | {notnull} | {default} | {pk} |\n")

                md_lines.append("\n")
            except Exception as e:
                md_lines.append(f"无法获取表结构: {e}\n\n")

        # 写入文件
        output_file = Path(output_path)
        try:
            output_file.write_text('\n'.join(md_lines), encoding='utf-8')
        except Exception as e:
            raise ChatExportError(f"写入文件失败: {e}")


def main():
    """命令行测试"""
    import sys

    if len(sys.argv) < 3:
        print("用法: python chat_export.py <数据库文件> <输出文件> [选项]")
        print()
        print("选项:")
        print("  --table <表名>        指定消息表名（默认: MSG）")
        print("  --limit <数量>        限制导出的消息数量")
        print("  --info                导出数据库结构信息")
        print()
        print("示例:")
        print("  # 导出聊天记录")
        print("  python chat_export.py MSG0_decrypted.db chat.md")
        print()
        print("  # 导出前100条消息")
        print("  python chat_export.py MSG0_decrypted.db chat.md --limit 100")
        print()
        print("  # 导出数据库结构")
        print("  python chat_export.py MSG0_decrypted.db db_info.md --info")
        sys.exit(1)

    db_path = sys.argv[1]
    output_path = sys.argv[2]

    # 解析选项
    table_name = "MSG"
    limit = None
    export_info = False

    i = 3
    while i < len(sys.argv):
        if sys.argv[i] == '--table' and i + 1 < len(sys.argv):
            table_name = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--limit' and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--info':
            export_info = True
            i += 1
        else:
            i += 1

    # 执行导出
    print("=" * 70)
    print("微信聊天记录导出")
    print("=" * 70)
    print(f"数据库: {db_path}")
    print(f"输出文件: {output_path}")
    print()

    try:
        with WeChatChatExporter(db_path) as exporter:
            if export_info:
                print("正在导出数据库结构信息...")
                exporter.export_database_info(output_path)
            else:
                print(f"正在导出聊天记录（表: {table_name}）...")
                if limit:
                    print(f"限制: {limit} 条消息")
                exporter.export_to_markdown(
                    output_path,
                    table_name=table_name,
                    limit=limit
                )

            print(f"✓ 导出成功!")
            print(f"输出文件: {Path(output_path).absolute()}")

    except ChatExportError as e:
        print(f"❌ 导出失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
