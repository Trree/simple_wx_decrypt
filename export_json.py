"""
微信消息导出JSON模块
按照 EchoTrace 思路实现：
1. 自动发现所有 message_*.db 分表
2. 通过 MD5(session_id) 定位消息表 Msg_{md5}
3. 跨数据库合并查询
4. 输出格式化的 JSON 文件
"""

import sqlite3
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict


class MessageTableNotFoundError(Exception):
    """消息表未找到"""
    pass


class WeChatJSONExporter:
    """
    微信聊天记录 JSON 导出器

    功能:
    - 自动发现 message_0.db ~ message_99.db
    - 通过 sessionId 的 MD5 定位表名 Msg_{MD5}
    - 跨数据库查询并合并结果
    - 输出格式化的 JSON
    """

    def __init__(self, decrypted_dir: str):
        """
        初始化导出器

        Args:
            decrypted_dir: 解密后的微信账号目录 (包含 message_*.db)
        """
        self.decrypted_dir = Path(decrypted_dir)
        self.message_dbs: List[Path] = []
        self.db_connections: Dict[str, sqlite3.Connection] = {}
        self.contact_cache: Dict[str, Dict[str, Any]] = {}  # 联系人信息缓存

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_all()

    def close_all(self):
        """关闭所有数据库连接"""
        for conn in self.db_connections.values():
            try:
                conn.close()
            except:
                pass
        self.db_connections.clear()

    def discover_message_databases(self) -> List[Path]:
        """
        发现所有消息数据库 (message_0.db ~ message_99.db)

        Returns:
            消息数据库文件路径列表
        """
        self.message_dbs = []

        # 检查多个可能的目录位置
        possible_dirs = [
            self.decrypted_dir,                          # 根目录
            self.decrypted_dir / "Msg",                  # Msg 子目录（旧版）
            self.decrypted_dir / "db_storage" / "message",  # 新版微信结构
        ]

        for base_dir in possible_dirs:
            if not base_dir.exists():
                continue

            # 扫描 message_0.db ~ message_99.db
            for i in range(100):
                db_path = base_dir / f"message_{i}.db"
                if db_path.exists() and db_path not in self.message_dbs:
                    self.message_dbs.append(db_path)

        print(f"✓ 发现 {len(self.message_dbs)} 个消息数据库")
        for db in self.message_dbs:
            print(f"  - {db.relative_to(self.decrypted_dir)}")

        return self.message_dbs

    def _get_connection(self, db_path: Path) -> sqlite3.Connection:
        """
        获取或创建数据库连接（带缓存）

        Args:
            db_path: 数据库文件路径

        Returns:
            数据库连接
        """
        db_key = str(db_path)
        if db_key not in self.db_connections:
            conn = sqlite3.connect(db_key)
            conn.row_factory = sqlite3.Row  # 返回字典形式
            self.db_connections[db_key] = conn
        return self.db_connections[db_key]

    def _calculate_md5(self, session_id: str) -> str:
        """
        计算 session_id 的 MD5 值

        Args:
            session_id: 会话ID (微信ID)

        Returns:
            32位小写MD5字符串
        """
        return hashlib.md5(session_id.encode('utf-8')).hexdigest()

    def _find_message_table(self, db_path: Path, session_id: str) -> Optional[str]:
        """
        在指定数据库中查找会话的消息表

        根据 EchoTrace 的规则:
        1. 精确匹配: Msg_{md5}
        2. 包含匹配: 表名包含完整MD5
        3. 部分匹配: 表名包含前24位MD5

        Args:
            db_path: 数据库文件路径
            session_id: 会话ID

        Returns:
            表名，未找到返回 None
        """
        conn = self._get_connection(db_path)
        cursor = conn.cursor()

        # 查询所有消息表
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'"
        )
        tables = [row[0] for row in cursor.fetchall()]

        if not tables:
            return None

        # 计算 MD5
        session_md5 = self._calculate_md5(session_id)

        # 1. 精确匹配
        expected_table = f'Msg_{session_md5}'
        for table in tables:
            if table.lower() == expected_table.lower():
                return table

        # 2. 包含完整 MD5
        for table in tables:
            if session_md5.lower() in table.lower():
                return table

        # 3. 部分 MD5 匹配（前24位）
        partial_md5 = session_md5[:24]
        for table in tables:
            if partial_md5.lower() in table.lower():
                return table

        return None

    def find_session_tables(self, session_id: str, silent: bool = False) -> List[Tuple[Path, str]]:
        """
        在所有消息数据库中查找会话的消息表

        Args:
            session_id: 会话ID
            silent: 是否静默模式（不打印查找信息）

        Returns:
            (数据库路径, 表名) 的列表
        """
        if not self.message_dbs:
            self.discover_message_databases()

        found_tables = []

        for db_path in self.message_dbs:
            table_name = self._find_message_table(db_path, session_id)
            if table_name:
                found_tables.append((db_path, table_name))
                if not silent:
                    print(f"  ✓ 在 {db_path.name} 中找到表 {table_name}")

        if not found_tables:
            raise MessageTableNotFoundError(
                f"未在任何数据库中找到会话 {session_id} 的消息表\n"
                f"MD5: {self._calculate_md5(session_id)}"
            )

        return found_tables

    def query_messages(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        跨数据库查询会话的所有消息

        Args:
            session_id: 会话ID
            limit: 限制返回消息数量（None=全部）

        Returns:
            消息列表（按时间排序）
        """
        tables = self.find_session_tables(session_id)
        all_messages = []

        print(f"\n正在查询会话 {session_id} 的消息...")

        for db_path, table_name in tables:
            conn = self._get_connection(db_path)
            cursor = conn.cursor()

            # 先获取表结构
            try:
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns_info = cursor.fetchall()
                available_columns = {row[1].lower(): row[1] for row in columns_info}  # 列名映射（小写 -> 原始）

                # 构建列名映射（处理不同版本的列名）
                column_map = {}

                # localId 列
                for possible_name in ['local_id', 'localId', 'localid', 'id', 'msgId', 'MsgId', '_id']:
                    if possible_name.lower() in available_columns:
                        column_map['local_id'] = available_columns[possible_name.lower()]
                        break

                # createTime 列
                for possible_name in ['create_time', 'createTime', 'createtime', 'time', 'timestamp', 'CreateTime']:
                    if possible_name.lower() in available_columns:
                        column_map['create_time'] = available_columns[possible_name.lower()]
                        break

                # type 列
                for possible_name in ['local_type', 'localType', 'type', 'Type', 'msgType', 'MsgType', 'message_type']:
                    if possible_name.lower() in available_columns:
                        column_map['type'] = available_columns[possible_name.lower()]
                        break

                # isSend 列
                for possible_name in ['is_send', 'isSend', 'issend', 'IsSender', 'sender', 'talker']:
                    if possible_name.lower() in available_columns:
                        column_map['is_send'] = available_columns[possible_name.lower()]
                        break

                # content 列
                for possible_name in ['message_content', 'content', 'Content', 'message', 'msg', 'msgContent']:
                    if possible_name.lower() in available_columns:
                        column_map['content'] = available_columns[possible_name.lower()]
                        break

                # compressContent 列（可选）
                for possible_name in ['compress_content', 'compressContent', 'compressed']:
                    if possible_name.lower() in available_columns:
                        column_map['compress_content'] = available_columns[possible_name.lower()]
                        break

                # source 列（可选）
                for possible_name in ['source', 'Source', 'msgSource']:
                    if possible_name.lower() in available_columns:
                        column_map['source'] = available_columns[possible_name.lower()]
                        break

                # real_sender_id 列（可选，群聊消息的发送者）
                for possible_name in ['real_sender_id', 'realSenderId', 'sender_id', 'senderId', 'sender']:
                    if possible_name.lower() in available_columns:
                        column_map['real_sender_id'] = available_columns[possible_name.lower()]
                        break

                # 构建 SELECT 语句
                select_parts = []
                if 'local_id' in column_map:
                    select_parts.append(f"{column_map['local_id']} as local_id")
                if 'create_time' in column_map:
                    select_parts.append(f"{column_map['create_time']} as create_time")
                if 'type' in column_map:
                    select_parts.append(f"{column_map['type']} as type")
                if 'is_send' in column_map:
                    select_parts.append(f"{column_map['is_send']} as is_send")
                else:
                    select_parts.append("0 as is_send")  # 默认值
                if 'content' in column_map:
                    select_parts.append(f"{column_map['content']} as content")
                if 'compress_content' in column_map:
                    select_parts.append(f"{column_map['compress_content']} as compress_content")
                if 'source' in column_map:
                    select_parts.append(f"{column_map['source']} as source")
                if 'real_sender_id' in column_map:
                    select_parts.append(f"{column_map['real_sender_id']} as real_sender_id")

                if not select_parts:
                    print(f"  ⚠ 表 {table_name} 没有可识别的列")
                    continue

                query = f"""
                    SELECT {', '.join(select_parts)}
                    FROM {table_name}
                """

                # 添加排序
                if 'create_time' in column_map:
                    query += f" ORDER BY {column_map['create_time']} DESC"

                if limit:
                    query += f" LIMIT {limit}"

                cursor.execute(query)
                rows = cursor.fetchall()

                for row in rows:
                    msg = dict(row)
                    msg['database'] = db_path.name
                    msg['table'] = table_name
                    all_messages.append(msg)

                print(f"  ✓ 从 {db_path.name}.{table_name} 查询到 {len(rows)} 条消息")

            except sqlite3.Error as e:
                print(f"  ✗ 查询失败: {e}")
                # 打印可用的列名供调试
                try:
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = [row[1] for row in cursor.fetchall()]
                    print(f"  可用列: {', '.join(columns)}")
                except:
                    pass
                continue

        # 按时间排序（降序，最新的在前）
        all_messages.sort(key=lambda x: x.get('create_time', 0), reverse=True)

        print(f"\n总计: {len(all_messages)} 条消息")
        return all_messages

    def get_contact_info(self, session_id: str) -> Dict[str, Any]:
        """
        获取联系人信息（从 contact.db 或 session.db）

        Args:
            session_id: 会话ID

        Returns:
            联系人信息字典
        """
        # 检查缓存
        if session_id in self.contact_cache:
            return self.contact_cache[session_id]

        contact_info = {
            'wxid': session_id,
            'nickname': '',
            'remark': '',
            'alias': ''
        }

        # 尝试多个可能的联系人数据库位置
        possible_contact_dbs = [
            self.decrypted_dir / "contact.db",
            self.decrypted_dir / "Msg" / "contact.db",
            self.decrypted_dir / "db_storage" / "contact" / "contact.db",
        ]

        for contact_db in possible_contact_dbs:
            if not contact_db.exists():
                continue

            try:
                conn = sqlite3.connect(str(contact_db))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # 尝试多个可能的表名
                possible_tables = ['contact', 'Contact', 'rcontact']

                for table_name in possible_tables:
                    try:
                        cursor.execute(
                            f"SELECT nick_name, remark, alias FROM {table_name} WHERE username = ?",
                            (session_id,)
                        )
                        row = cursor.fetchone()

                        if row:
                            contact_info['nickname'] = row['nick_name'] or ''
                            contact_info['remark'] = row['remark'] or ''
                            contact_info['alias'] = row['alias'] or ''
                            conn.close()
                            # 缓存结果
                            self.contact_cache[session_id] = contact_info
                            return contact_info
                    except:
                        continue

                conn.close()
            except Exception as e:
                print(f"  ⚠ 获取联系人信息失败: {e}")
                continue

        # 缓存结果（即使是空的）
        self.contact_cache[session_id] = contact_info
        return contact_info

    def get_sender_display_name(self, sender_wxid: str) -> str:
        """
        获取发送者的显示名称

        Args:
            sender_wxid: 发送者的微信ID

        Returns:
            显示名称（优先级：备注 > 昵称 > wxid）
        """
        if not sender_wxid:
            return ''

        contact = self.get_contact_info(sender_wxid)
        return contact.get('remark') or contact.get('nickname') or sender_wxid

    def _parse_source_xml(self, source: str) -> Dict[str, Any]:
        """
        解析 source 字段中的 XML 数据

        Args:
            source: XML 格式的来源数据

        Returns:
            解析后的字典
        """
        import xml.etree.ElementTree as ET

        result = {}

        if not source or not isinstance(source, str):
            return result

        try:
            root = ET.fromstring(source)

            # 提取常见字段
            result['type'] = root.get('type', '')

            # 引用消息信息
            appmsg = root.find('appmsg')
            if appmsg is not None:
                result['title'] = appmsg.findtext('title', '')
                result['des'] = appmsg.findtext('des', '')

                # 引用的原始消息
                refermsg = appmsg.find('refermsg')
                if refermsg is not None:
                    result['referMsg'] = {
                        'type': refermsg.findtext('type', ''),
                        'content': refermsg.findtext('content', ''),
                        'displayName': refermsg.findtext('displayname', ''),
                    }

        except Exception:
            pass

        return result

    def _safe_decode(self, data: Any, field_name: str = '') -> str:
        """
        安全解码数据，处理 bytes、二进制、压缩数据等各种格式

        Args:
            data: 要解码的数据
            field_name: 字段名（用于判断是否需要特殊处理）

        Returns:
            解码后的字符串
        """
        if data is None:
            return ''

        if isinstance(data, str):
            return data

        if isinstance(data, bytes):
            # 步骤1：检查并尝试 Zstandard 解压缩
            # Zstandard magic numbers: 0x28B52FFD (little-endian) 或 0xFD2FB528 (big-endian)
            if len(data) >= 4:
                magic = int.from_bytes(data[:4], 'little')
                if magic == 0x28B52FFD or magic == 0xFD2FB528:
                    try:
                        import zstandard as zstd
                        dctx = zstd.ZstdDecompressor()
                        decompressed = dctx.decompress(data)
                        # 解压成功，递归处理解压后的数据
                        return self._safe_decode(decompressed, field_name)
                    except ImportError:
                        # 如果没有安装 zstandard 库，提示用户
                        print("警告: 检测到 zstd 压缩数据，但未安装 zstandard 库")
                        print("请运行: pip install zstandard")
                    except Exception as e:
                        # zstd 解压失败，继续尝试其他方式
                        pass

            # 步骤2：尝试 zlib 解压缩
            # 压缩数据通常以特定字节开头，如 0x78 0x9C (默认压缩) 或 0x78 0xDA (最佳压缩)
            try:
                import zlib
                decompressed = zlib.decompress(data)
                # 解压成功，递归处理解压后的数据
                return self._safe_decode(decompressed, field_name)
            except:
                # 解压失败，继续尝试直接解码
                pass

            # 步骤3：尝试多种编码直接解码
            for encoding in ['utf-8', 'gbk', 'gb2312', 'latin1']:
                try:
                    decoded = data.decode(encoding, errors='ignore')
                    # 检查是否为可打印字符（包含XML常见字符）
                    if decoded and (
                        decoded.startswith('<') or  # XML数据
                        all(c.isprintable() or c in '\n\r\t' for c in decoded[:100])
                    ):
                        return decoded
                except:
                    continue

            # 步骤4：如果都失败，返回 base64 编码
            import base64
            return f"[二进制数据: {base64.b64encode(data[:100]).decode()}{'...' if len(data) > 100 else ''}]"

        return str(data)

    def format_message_type(self, type_code: int) -> str:
        """
        格式化消息类型

        Args:
            type_code: 消息类型代码

        Returns:
            类型描述
        """
        type_map = {
            1: '文本消息',
            3: '图片消息',
            34: '语音消息',
            42: '名片消息',
            43: '视频消息',
            47: '动画表情',
            48: '位置消息',
            49: '链接/文件/引用消息',  # 需要解析 source
            50: '通话消息',
            10000: '系统消息',
            10002: '撤回消息',
            244813135921: '引用消息',  # 新版微信
            17179869233: '卡片式链接',
            21474836529: '图文消息',
            154618822705: '小程序分享',
            12884901937: '音乐卡片',
            8594229559345: '红包卡片',
            81604378673: '聊天记录合并转发',
            266287972401: '拍一拍消息',
            8589934592049: '转账卡片',
            270582939697: '视频号直播卡片',
            25769803825: '文件消息',
            34359738417: '文件消息',
            103079215153: '文件消息',
        }
        return type_map.get(type_code, f'未知类型({type_code})')

    def format_timestamp(self, timestamp: int) -> str:
        """
        格式化时间戳

        Args:
            timestamp: Unix 时间戳（秒）

        Returns:
            格式化的时间字符串
        """
        try:
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return ''

    def export_session_to_json(
        self,
        session_id: str,
        output_path: str,
        limit: Optional[int] = None,
        indent: int = 2
    ) -> bool:
        """
        导出会话消息为 JSON 文件

        Args:
            session_id: 会话ID
            output_path: 输出文件路径
            limit: 限制消息数量（None=全部）
            indent: JSON缩进空格数

        Returns:
            成功返回 True，失败返回 False
        """
        try:
            print(f"\n{'='*70}")
            print(f"导出会话: {session_id}")
            print(f"{'='*70}\n")

            # 获取联系人信息
            contact_info = self.get_contact_info(session_id)

            # 查询消息
            messages = self.query_messages(session_id, limit)

            # 格式化消息
            formatted_messages = []
            for msg in messages:
                # 安全解码各个字段
                raw_content = self._safe_decode(msg.get('content', ''), 'content')
                source = self._safe_decode(msg.get('source', ''), 'source')

                # 处理 content：对于引用消息（type 244813135921），从 XML 中提取 title
                content = raw_content
                msg_type = msg.get('type', 0)

                # 检查是否为引用消息的 XML 格式
                if msg_type == 244813135921 and raw_content:
                    # 尝试从 XML 中提取 title
                    if '<?xml' in raw_content or '<msg>' in raw_content:
                        try:
                            import xml.etree.ElementTree as ET
                            # 移除可能的前缀（如 "SunnyUIBE:\n"）
                            xml_start = raw_content.find('<?xml')
                            if xml_start == -1:
                                xml_start = raw_content.find('<msg>')

                            if xml_start >= 0:
                                xml_content = raw_content[xml_start:]
                                root = ET.fromstring(xml_content)

                                # 提取 title
                                title_elem = root.find('.//title')
                                if title_elem is not None and title_elem.text:
                                    content = title_elem.text
                        except:
                            # XML 解析失败，保持原内容
                            pass

                # 获取发送者信息（群聊消息）
                sender_id = msg.get('real_sender_id', '')
                if isinstance(sender_id, bytes):
                    sender_id = self._safe_decode(sender_id, 'real_sender_id')

                # 清理空字符串为 None
                if not sender_id or sender_id == '':
                    sender_id = None

                # 获取发送者显示名称
                if sender_id:
                    # 群聊消息：使用发送者的联系人信息
                    sender_display_name = self.get_sender_display_name(sender_id)
                else:
                    # 私聊消息：使用会话联系人的显示名称
                    sender_display_name = contact_info.get('remark') or contact_info.get('nickname') or contact_info['wxid']

                # 构建消息对象（与 EchoTrace 格式一致）
                formatted_msg = {
                    'localId': msg.get('local_id'),
                    'createTime': msg.get('create_time'),
                    'formattedTime': self.format_timestamp(msg.get('create_time', 0)),
                    'type': self.format_message_type(msg_type),
                    'localType': msg_type,
                    'content': content,
                    'isSend': msg.get('is_send', 0),
                    'senderUsername': sender_id,  # 群聊消息的发送者 wxid，私聊为 None
                    'senderDisplayName': sender_display_name,  # 发送者显示名称
                    'senderAvatarKey': sender_id,  # 头像键，与 senderUsername 相同
                    'source': source,  # 消息来源（XML格式）
                }

                formatted_messages.append(formatted_msg)

            # 构建输出数据（与 EchoTrace 格式一致）
            output_data = {
                'session': {
                    'wxid': contact_info['wxid'],
                    'nickname': contact_info['nickname'],
                    'remark': contact_info['remark'],
                    'alias': contact_info['alias'],
                    'displayName': contact_info['remark'] or contact_info['nickname'] or contact_info['wxid'],
                    'messageCount': len(messages),  # 添加消息数量到 session 中
                },
                'messages': formatted_messages,
                'exportTime': datetime.now().isoformat(),
            }

            # 写入 JSON 文件
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=indent)

            print(f"\n{'='*70}")
            print(f"✓ 导出成功")
            print(f"{'='*70}")
            print(f"输出文件: {output_file}")
            print(f"消息总数: {len(messages)}")
            print(f"文件大小: {output_file.stat().st_size / 1024:.2f} KB")
            print(f"{'='*70}\n")

            return True

        except Exception as e:
            print(f"\n✗ 导出失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def list_all_sessions(self, count_messages: bool = True) -> List[Dict[str, Any]]:
        """
        列出所有会话（优先从 session.db，否则从消息表扫描）

        Args:
            count_messages: 是否统计每个会话的消息数量（较慢但准确）

        Returns:
            会话列表
        """
        # 方法1: 尝试从 session.db / MicroMsg.db 读取
        sessions = self._list_sessions_from_session_db()

        if sessions:
            print(f"✓ 从会话数据库获取到 {len(sessions)} 个会话")
        else:
            # 方法2: 从消息数据库扫描所有 Msg_ 表
            print("⚠ 未找到会话数据库，改为扫描消息表...")
            sessions = self._list_sessions_from_message_tables()

            if sessions:
                print(f"✓ 从消息表扫描到 {len(sessions)} 个会话")

        # 统计每个会话的实际消息数量
        if count_messages and sessions:
            print("\n正在统计消息数量...")
            sessions = self._count_session_messages(sessions)

        return sessions

    def _count_session_messages(self, sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        统计每个会话的实际消息数量

        Args:
            sessions: 会话列表

        Returns:
            更新了消息数量的会话列表
        """
        if not self.message_dbs:
            self.discover_message_databases()

        total = len(sessions)
        for idx, session in enumerate(sessions, 1):
            session_id = session['username']
            total_count = 0

            # 查找该会话在所有数据库中的消息表
            try:
                tables = self.find_session_tables(session_id)

                for db_path, table_name in tables:
                    conn = self._get_connection(db_path)
                    cursor = conn.cursor()

                    try:
                        cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                        result = cursor.fetchone()
                        count = result[0] if result else 0
                        total_count += count
                    except:
                        pass

                session['messageCount'] = total_count

                # 显示进度
                if idx % 10 == 0 or idx == total:
                    print(f"  进度: {idx}/{total} 已处理")

            except MessageTableNotFoundError:
                session['messageCount'] = 0
            except Exception:
                session['messageCount'] = 0

        # 按消息数量降序排序
        sessions.sort(key=lambda x: x['messageCount'], reverse=True)

        # 过滤掉没有消息的会话
        sessions = [s for s in sessions if s['messageCount'] > 0]

        return sessions

    def _list_sessions_from_session_db(self) -> List[Dict[str, Any]]:
        """从 session.db 或类似数据库读取会话列表"""
        sessions = []

        # 尝试多个可能的数据库文件
        possible_dbs = [
            # 旧版结构
            self.decrypted_dir / "session.db",
            self.decrypted_dir / "Msg" / "session.db",
            self.decrypted_dir / "MicroMsg.db",
            self.decrypted_dir / "Msg" / "MicroMsg.db",
            self.decrypted_dir / "EnMicroMsg.db",
            self.decrypted_dir / "contact.db",
            self.decrypted_dir / "Msg" / "contact.db",
            # 新版结构 (db_storage)
            self.decrypted_dir / "db_storage" / "session" / "session.db",
            self.decrypted_dir / "db_storage" / "contact" / "contact.db",
            self.decrypted_dir / "db_storage" / "general" / "MicroMsg.db",
        ]

        for session_db in possible_dbs:
            if not session_db.exists():
                continue

            try:
                conn = sqlite3.connect(str(session_db))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # 尝试多个可能的表名
                possible_tables = ['SessionTable', 'Session', 'rcontact', 'Contact', 'contact']

                for table_name in possible_tables:
                    try:
                        # 先检查表是否存在
                        cursor.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                            (table_name,)
                        )
                        if not cursor.fetchone():
                            continue

                        # 获取表的列信息
                        cursor.execute(f"PRAGMA table_info({table_name})")
                        columns = {row[1] for row in cursor.fetchall()}

                        # 构建查询语句
                        select_cols = []
                        if 'username' in columns:
                            select_cols.append('username')
                        elif 'alias' in columns:
                            select_cols.append('alias as username')

                        if 'display_name' in columns:
                            select_cols.append('display_name')
                        elif 'nick_name' in columns:
                            select_cols.append('nick_name as display_name')
                        elif 'remark' in columns:
                            select_cols.append('remark as display_name')

                        if not select_cols:
                            continue

                        # 查询数据
                        query = f"SELECT {', '.join(select_cols)} FROM {table_name}"

                        # 添加排序
                        if 'sort_timestamp' in columns:
                            query += " ORDER BY sort_timestamp DESC"

                        query += " LIMIT 1000"

                        cursor.execute(query)

                        for row in cursor.fetchall():
                            username = row['username'] if 'username' in row.keys() else ''
                            display_name = row['display_name'] if 'display_name' in row.keys() else username

                            if username:
                                sessions.append({
                                    'username': username,
                                    'displayName': display_name or username,
                                    'lastTime': 0,
                                    'messageCount': 0
                                })

                        if sessions:
                            conn.close()
                            return sessions

                    except sqlite3.Error:
                        continue

                conn.close()

            except Exception:
                continue

        return sessions

    def _list_sessions_from_message_tables(self) -> List[Dict[str, Any]]:
        """从消息数据库的 Msg_ 表中提取会话列表"""
        if not self.message_dbs:
            self.discover_message_databases()

        sessions_dict = {}  # 使用字典去重

        for db_path in self.message_dbs:
            try:
                conn = self._get_connection(db_path)
                cursor = conn.cursor()

                # 查询所有 Msg_ 表
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'"
                )
                tables = [row[0] for row in cursor.fetchall()]

                print(f"  扫描 {db_path.name}: 找到 {len(tables)} 个消息表")

                # 尝试从 Name2Id 表反推会话信息
                try:
                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='Name2Id'"
                    )
                    if cursor.fetchone():
                        cursor.execute("SELECT user_name FROM Name2Id LIMIT 1000")
                        for row in cursor.fetchall():
                            username = row[0]
                            if username and username not in sessions_dict:
                                sessions_dict[username] = {
                                    'username': username,
                                    'displayName': username,
                                    'lastTime': 0,
                                    'messageCount': 0
                                }
                except:
                    pass

            except Exception as e:
                print(f"  ⚠ 扫描 {db_path.name} 失败: {e}")
                continue

        # 获取联系人信息完善显示名称
        possible_contact_dbs = [
            self.decrypted_dir / "contact.db",
            self.decrypted_dir / "Msg" / "contact.db",
            self.decrypted_dir / "db_storage" / "contact" / "contact.db",
        ]

        for contact_db in possible_contact_dbs:
            if not contact_db.exists():
                continue

            try:
                conn = sqlite3.connect(str(contact_db))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # 尝试多个可能的表名
                possible_tables = ['contact', 'Contact', 'rcontact']

                for table_name in possible_tables:
                    try:
                        for username in list(sessions_dict.keys()):
                            try:
                                cursor.execute(
                                    f"SELECT nick_name, remark FROM {table_name} WHERE username = ?",
                                    (username,)
                                )
                                row = cursor.fetchone()
                                if row:
                                    display_name = row['remark'] or row['nick_name'] or username
                                    sessions_dict[username]['displayName'] = display_name
                            except:
                                pass
                        break  # 成功处理了一个表，退出循环
                    except:
                        continue

                conn.close()
                break  # 成功处理了一个数据库，退出循环
            except:
                pass

        return list(sessions_dict.values())


def main():
    """命令行入口示例"""
    import argparse

    parser = argparse.ArgumentParser(
        description='微信消息导出为 JSON（支持分表）'
    )
    parser.add_argument(
        '-d', '--dir',
        required=True,
        help='解密后的微信账号目录'
    )
    parser.add_argument(
        '-s', '--session',
        help='会话ID (微信ID)'
    )
    parser.add_argument(
        '-o', '--output',
        help='输出JSON文件路径'
    )
    parser.add_argument(
        '-l', '--limit',
        type=int,
        help='限制消息数量'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='列出所有会话'
    )

    args = parser.parse_args()

    with WeChatJSONExporter(args.dir) as exporter:
        # 发现数据库
        exporter.discover_message_databases()

        # 列出会话
        if args.list:
            print("\n所有会话:")
            print("=" * 70)
            sessions = exporter.list_all_sessions()
            for i, session in enumerate(sessions, 1):
                print(f"{i}. {session['displayName']} ({session['username']})")
                print(f"   消息数: {session['messageCount']}")
            print("=" * 70)
            return

        # 导出会话
        if args.session:
            output = args.output or f"{args.session}_chat_history.json"
            exporter.export_session_to_json(
                args.session,
                output,
                limit=args.limit
            )
        else:
            print("请指定 --session 或使用 --list 查看所有会话")


if __name__ == '__main__':
    main()
