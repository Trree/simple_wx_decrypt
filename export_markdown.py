"""
微信消息导出 Markdown 模块
将微信聊天记录导出为简洁的 Markdown 格式，类似聊天记录
"""

from pathlib import Path
from typing import Dict, Any, Optional
from export_json import WeChatJSONExporter, MessageTableNotFoundError


# 消息类型到标签的映射
TYPE_TAG_MAP = {
    '图片消息': '[图片]',
    '语音消息': '[语音]',
    '视频消息': '[视频]',
    '动画表情': '[表情]',
    '位置消息': '[位置]',
    '名片消息': '[名片]',
    '文件消息': '[文件]',
    '通话消息': '[通话]',
    '撤回消息': '[已撤回]',
    '小程序分享': '[小程序]',
    '音乐卡片': '[音乐]',
    '红包卡片': '[红包]',
    '转账卡片': '[转账]',
    '聊天记录卡片': '[聊天记录]',
    '链接卡片': '[链接]',
    '卡片式链接': '[链接]',
    # 文本消息和引用消息会显示内容，不需要标签
    # 系统消息会特殊处理
}


class WeChatMarkdownExporter:
    """
    微信聊天记录 Markdown 导出器

    功能:
    - 复用 WeChatJSONExporter 的数据查询能力
    - 将消息格式化为简洁的 Markdown 格式
    - 支持群聊和私聊
    - 特殊消息类型显示为类型标签
    """

    def __init__(self, decrypted_dir: str):
        """
        初始化 Markdown 导出器

        Args:
            decrypted_dir: 解密后的微信账号目录
        """
        self.decrypted_dir = Path(decrypted_dir)
        self.json_exporter = WeChatJSONExporter(decrypted_dir)

    def __enter__(self):
        """上下文管理器入口"""
        self.json_exporter.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.json_exporter.__exit__(exc_type, exc_val, exc_tb)

    def _get_message_type_tag(self, type_str: str) -> Optional[str]:
        """
        获取消息类型对应的标签

        Args:
            type_str: 消息类型字符串（如 "图片消息"）

        Returns:
            类型标签（如 "[图片]"）或 None
        """
        return TYPE_TAG_MAP.get(type_str)

    def format_message_markdown(self, msg: Dict[str, Any], session_info: Dict[str, Any]) -> str:
        """
        将单条消息格式化为 Markdown 格式

        Args:
            msg: 消息字典
            session_info: 会话信息字典

        Returns:
            格式化后的 Markdown 消息行
        """
        # 获取时间戳（使用 json_exporter 的方法格式化）
        timestamp = msg.get('create_time', 0)
        time_str = self.json_exporter.format_timestamp(timestamp) if timestamp else '未知时间'

        # 获取消息类型
        msg_type_code = msg.get('type', 0)
        msg_type = self.json_exporter.format_message_type(msg_type_code)

        # 安全解码消息内容（处理 bytes、压缩数据等）
        raw_content = msg.get('content', '')
        content = self.json_exporter._safe_decode(raw_content, 'content')

        # 对于引用消息（type 244813135921），尝试从 XML 中提取 title
        if msg_type_code == 244813135921 and content:
            if '<?xml' in content or '<msg>' in content:
                try:
                    import xml.etree.ElementTree as ET
                    xml_start = content.find('<?xml')
                    if xml_start == -1:
                        xml_start = content.find('<msg>')

                    if xml_start >= 0:
                        xml_content = content[xml_start:]
                        root = ET.fromstring(xml_content)
                        title_elem = root.find('.//title')
                        if title_elem is not None and title_elem.text:
                            content = title_elem.text
                except:
                    pass

        # 去除首尾空格
        content = content.strip()

        # 判断是否是发送的消息
        is_send = msg.get('is_send', 0) == 1

        # 获取发送者名称
        if is_send:
            sender_name = "我"
        else:
            # 尝试从消息中获取发送者信息（群聊）
            sender_id = msg.get('real_sender_id', '')
            if isinstance(sender_id, bytes):
                sender_id = self.json_exporter._safe_decode(sender_id, 'real_sender_id')

            if sender_id:
                # 群聊消息：获取发送者的显示名称
                sender_name = self.json_exporter.get_sender_display_name(sender_id)
            else:
                # 私聊消息：使用会话的显示名称
                sender_name = session_info.get('displayName', '未知发送者')

            # 如果 sender_name 是数字，转换为字符串
            if isinstance(sender_name, (int, float)):
                sender_name = str(sender_name)

        # 处理系统消息
        if msg_type == '系统消息':
            return f"[{time_str}] 系统: {content}"

        # 获取类型标签
        type_tag = self._get_message_type_tag(msg_type)

        # 格式化消息
        if type_tag:
            # 特殊消息类型（图片、语音、视频等）
            if content:
                # 如果有内容，显示标签 + 内容
                formatted_content = f"{type_tag} {content}"
            else:
                # 如果没有内容，只显示标签
                formatted_content = type_tag
        elif msg_type == '引用消息':
            # 引用消息：直接显示内容（已从 XML 中提取）
            formatted_content = content if content else "[引用]"
        elif msg_type == '文本消息' or not msg_type:
            # 普通文本消息：直接显示内容
            formatted_content = content if content else "(空消息)"
        else:
            # 未知类型：显示类型 + 内容
            if content:
                formatted_content = f"[{msg_type}] {content}"
            else:
                formatted_content = f"[{msg_type}]"

        return f"[{time_str}] {sender_name}: {formatted_content}"

    def export_session_to_markdown(
        self,
        session_id: str,
        output_path: str,
        limit: Optional[int] = None
    ) -> bool:
        """
        导出会话到 Markdown 文件

        Args:
            session_id: 会话 ID (微信 ID)
            output_path: 输出 Markdown 文件路径
            limit: 限制消息数量（可选）

        Returns:
            是否成功
        """
        try:
            print(f"\n正在导出会话: {session_id}")
            print("=" * 70)

            # 发现数据库
            self.json_exporter.discover_message_databases()

            # 获取会话信息
            print(f"\n正在获取会话信息...")
            session_info = self.json_exporter.get_contact_info(session_id)
            print(f"✓ 会话: {session_info.get('displayName', session_id)}")

            # 查询消息
            print(f"\n正在查询消息...")
            messages = self.json_exporter.query_messages(session_id, limit=limit)

            if not messages:
                print("✗ 未找到任何消息")
                return False

            print(f"✓ 找到 {len(messages)} 条消息")

            # 格式化消息为 Markdown
            print(f"\n正在格式化为 Markdown...")
            markdown_lines = []

            for msg in messages:
                try:
                    line = self.format_message_markdown(msg, session_info)
                    markdown_lines.append(line)
                except Exception as e:
                    # 如果单条消息格式化失败，记录但继续处理
                    print(f"  警告: 消息 {msg.get('localId')} 格式化失败: {e}")
                    continue

            # 写入文件
            output_file = Path(output_path)
            print(f"\n正在写入文件: {output_file}")

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(markdown_lines))

            print(f"✓ 导出成功!")
            print(f"  - 消息数: {len(markdown_lines)}")
            print(f"  - 文件路径: {output_file.absolute()}")
            print(f"  - 文件大小: {output_file.stat().st_size:,} 字节")
            print("=" * 70)

            return True

        except MessageTableNotFoundError as e:
            print(f"\n✗ 错误: {e}")
            return False
        except Exception as e:
            print(f"\n✗ 导出失败: {e}")
            import traceback
            traceback.print_exc()
            return False
