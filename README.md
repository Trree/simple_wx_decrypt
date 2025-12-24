# 微信数据解密工具 (Python 版本)

完美复刻 EchoTrace 的 Go 解密核心代码，使用 Python 3.12 实现。

## 特性

✨ **完整功能**
- 🔓 数据库解密 (Windows V4)
- 🖼️ 图片解密 (V3, V4-V1, V4-V2)
- 📝 聊天记录导出 (Markdown 格式)
- ✅ 密钥验证
- 🔍 XOR 密钥自动检测
- 📊 进度显示

🎯 **完美复刻**
- 与 Go 版本 100% 算法一致
- 完整的 PBKDF2-SHA512 + AES-256-CBC + HMAC-SHA512 实现
- 精确复制所有常量和逻辑

🚀 **易于使用**
- 纯 Python 实现，无需编译
- 统一的命令行接口
- 详细的错误提示和进度显示

## 环境要求

- **Python**: 3.12+ (推荐 3.12)
- **操作系统**: Windows / Linux / macOS
- **依赖库**: `cryptography` (自动安装)

## 安装

### 1. 克隆或下载代码

```bash
cd python_decrypt
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

或手动安装：

```bash
pip install cryptography
```

## 使用方法

### 📘 数据库解密

解密微信加密数据库（MSG0.db、MicroMsg.db 等）：

```bash
python wechat_decrypt.py db -i MSG0.db -o MSG0_decrypted.db -k 0123456789abcdef...
```

**参数说明**：
- `-i, --input`: 输入的加密数据库文件
- `-o, --output`: 输出的解密数据库文件
- `-k, --key`: 64 位十六进制密钥
- `--skip-validation`: 跳过密钥验证（不推荐）
- `-q, --quiet`: 安静模式，不显示进度条

**示例**：

```bash
# 基本用法
python wechat_decrypt.py db \
  -i "C:/Users/YourName/Documents/WeChat Files/wxid_xxx/Msg/MSG0.db" \
  -o MSG0_decrypted.db \
  -k 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef

# 静默模式（不显示进度）
python wechat_decrypt.py db -i MSG0.db -o output.db -k 0123...cdef --quiet
```

### 🔑 验证密钥

在解密前验证密钥是否正确：

```bash
python wechat_decrypt.py validate -i MSG0.db -k 0123456789abcdef...
```

**输出示例**：

```
======================================================================
密钥验证
======================================================================

数据库文件: E:\1\3\echotrace\python_decrypt\MSG0.db
密钥: 0123456789abcdef...0123456789abcdef

正在验证... ✓ 密钥正确

✓ 此密钥可用于解密该数据库
```

### 🖼️ 图片解密

解密微信加密图片（.dat 文件）：

```bash
python wechat_decrypt.py image -i image.dat -o image.jpg -x 123
```

**参数说明**：
- `-i, --input`: 输入的 .dat 文件
- `-o, --output`: 输出的图片文件（自动检测格式）
- `-x, --xor-key`: XOR 密钥（0-255）
- `-a, --aes-key`: AES 密钥（16 字符，可选）

**示例**：

```bash
# V3 版本（仅 XOR）
python wechat_decrypt.py image -i image.dat -o image.jpg -x 123

# V4 版本（AES + XOR）
python wechat_decrypt.py image -i image.dat -o image.jpg -x 123 -a customaeskey123
```

### 🔍 自动检测 XOR 密钥

自动检测图片的 XOR 密钥（针对 V3 版本）：

```bash
python wechat_decrypt.py detect -i image.dat
```

**输出示例**：

```
======================================================================
XOR 密钥检测
======================================================================

正在分析文件: E:\1\3\echotrace\python_decrypt\image.dat
----------------------------------------------------------------------
文件版本: V3 (简单 XOR)
正在检测 XOR 密钥... ✓ 检测成功

XOR 密钥: 123 (0x7B)

使用方法:
  python wechat_decrypt.py image -i image.dat -o output.jpg -x 123
```

### 📊 显示文件信息

查看数据库或图片文件的详细信息：

```bash
python wechat_decrypt.py info -i MSG0.db
```

**输出示例**：

```
======================================================================
文件信息
======================================================================

文件路径: E:\1\3\echotrace\python_decrypt\MSG0.db
文件大小: 15.23 MB (15,974,400 字节)

数据库信息:
  页面总数: 3,900
  页面大小: 4096 字节
  盐值: 1234567890abcdef1234567890abcdef
  加密状态: 是
```

### 📝 导出聊天记录

将解密后的数据库中的聊天记录导出为 Markdown 格式：

```bash
python wechat_decrypt.py export -i MSG0_decrypted.db -o chat.md
```

**参数说明**：
- `-i, --input`: 解密后的数据库文件
- `-o, --output`: 输出的 Markdown 文件路径
- `--table`: 消息表名（默认: MSG）
- `--limit`: 限制导出的消息数量（可选）
- `--title`: Markdown 文档标题（可选）
- `--info`: 导出数据库结构信息而非聊天记录

**示例**：

```bash
# 导出全部聊天记录
python wechat_decrypt.py export -i MSG0_decrypted.db -o chat.md

# 导出前 100 条消息
python wechat_decrypt.py export -i MSG0_decrypted.db -o chat.md --limit 100

# 指定自定义标题
python wechat_decrypt.py export -i MSG0_decrypted.db -o chat.md --title "我的微信聊天记录"

# 导出数据库结构信息
python wechat_decrypt.py export -i MSG0_decrypted.db -o db_structure.md --info
```

**输出示例**：

导出的 Markdown 文件包含：
- 📊 统计信息（消息总数、消息类型分布）
- 💬 格式化的聊天记录（时间、发送者、消息类型、内容）
- 🗂️ 清晰的层级结构，便于阅读

**Markdown 格式预览**：

```markdown
# 微信聊天记录

> 导出时间: 2024-12-24 10:30:00
> 数据库: MSG0_decrypted.db
> 消息表: MSG

## 📊 统计信息
- 总消息数: 1,234
- 导出消息数: 1,234

### 消息类型分布
- 文本: 1,100
- 图片: 80
- 语音: 30
- 系统消息: 24

## 💬 聊天记录
> 共 1234 条消息

---

### 消息 #1

- **时间**: 2024-12-20 09:15:23
- **发送者**: 我
- **类型**: 文本
- **内容**:

  > 早上好！

---

### 消息 #2

- **时间**: 2024-12-20 09:16:45
- **发送者**: wxid_abc123
- **类型**: 文本
- **内容**:

  > 早上好！今天天气不错
```

## 核心模块

### decrypt_core.py - 数据库解密核心

**核心类**: `WeChatDBDecryptor`

**主要方法**：

```python
from decrypt_core import WeChatDBDecryptor

# 创建解密器
decryptor = WeChatDBDecryptor()

# 验证密钥
is_valid = decryptor.validate_key('MSG0.db', 'hex_key')

# 解密数据库
decryptor.decrypt_database(
    input_path='MSG0.db',
    output_path='MSG0_decrypted.db',
    hex_key='0123...cdef',
    progress_callback=lambda current, total: print(f"{current}/{total}")
)

# 获取数据库信息
info = decryptor.get_database_info('MSG0.db')
```

**技术细节**：

```
密钥派生: PBKDF2-SHA512 (256,000 次迭代)
加密算法: AES-256-CBC
完整性校验: HMAC-SHA512
页面大小: 4096 字节
```

### image_decrypt.py - 图片解密核心

**核心类**: `WeChatImageDecryptor`

**主要方法**：

```python
from image_decrypt import WeChatImageDecryptor

# 检测版本
version = WeChatImageDecryptor.get_dat_version('image.dat')
# 返回: 0=V3, 1=V4-V1, 2=V4-V2

# V3 解密（XOR）
data = WeChatImageDecryptor.decrypt_dat_v3('image.dat', xor_key=123)

# V4 解密（AES + XOR）
data = WeChatImageDecryptor.decrypt_dat_v4(
    'image.dat',
    xor_key=123,
    aes_key=b'cfcd208495d565ef'
)

# 自动解密（推荐）
version_str = WeChatImageDecryptor.auto_decrypt_dat(
    input_path='image.dat',
    output_path='image.jpg',
    xor_key=123
)

# 检测 XOR 密钥
xor_key = WeChatImageDecryptor.detect_xor_key('image.dat')
```

### chat_export.py - 聊天记录导出核心

**核心类**: `WeChatChatExporter`

**主要方法**：

```python
from chat_export import WeChatChatExporter

# 使用上下文管理器
with WeChatChatExporter('MSG0_decrypted.db') as exporter:
    # 获取所有表
    tables = exporter.get_tables()

    # 获取表信息
    columns = exporter.get_table_info('MSG')

    # 获取记录数
    count = exporter.get_table_count('MSG')

    # 查询消息
    messages = exporter.query_messages(
        table_name='MSG',
        limit=100,
        where_clause="Type=1"  # 只查询文本消息
    )

    # 导出到 Markdown
    exporter.export_to_markdown(
        output_path='chat.md',
        table_name='MSG',
        limit=1000,
        title='我的微信聊天记录'
    )

    # 导出数据库结构
    exporter.export_database_info('db_structure.md')
```

**支持的消息类型**：

| 类型代码 | 说明 |
|---------|------|
| 1 | 文本消息 |
| 3 | 图片消息 |
| 34 | 语音消息 |
| 42 | 名片消息 |
| 43 | 视频消息 |
| 47 | 表情消息 |
| 48 | 位置消息 |
| 49 | 链接/文件消息 |
| 50 | 语音通话 |
| 10000 | 系统消息 |

## 技术原理

### 数据库解密流程

```
1. 读取第一页（4096 字节）
   ↓
2. 提取 Salt（前 16 字节）
   ↓
3. 密钥派生
   ├─ PBKDF2-SHA512(key, salt, 256000) → enc_key
   └─ PBKDF2-SHA512(enc_key, salt⊕0x3a, 2) → mac_key
   ↓
4. 逐页解密
   ├─ 验证 HMAC-SHA512
   ├─ 提取 IV（16 字节）
   ├─ AES-256-CBC 解密
   └─ 拼接结果
   ↓
5. 输出标准 SQLite 数据库
```

### 图片解密流程

**V3 版本**：

```
简单 XOR：data[i] = encrypted[i] XOR key
```

**V4 版本**：

```
文件结构:
[6B 签名][4B AES大小][4B XOR大小][1B 保留]
[AES加密数据][原始数据][XOR加密数据]

解密步骤:
1. 解析文件头
2. AES-ECB 解密 → 去除 PKCS7 填充
3. XOR 解密
4. 拼接: AES解密 + 原始 + XOR解密
```

## 常见问题

### Q: 如何获取解密密钥？

A: 密钥需要从微信进程中提取，本工具不提供密钥提取功能。你可以使用第三方工具（如 WeChatDecrypt、SharpWxDump 等）获取密钥。

### Q: 为什么提示"密钥错误"？

A: 可能的原因：
1. 密钥不正确（长度必须是 64 位十六进制字符）
2. 数据库文件损坏
3. 数据库版本不支持（当前仅支持 Windows V4）

### Q: 解密后的数据库如何查看？

A: 解密后是标准的 SQLite 数据库，可以使用以下工具打开：
- DB Browser for SQLite
- SQLiteStudio
- Navicat
- Python: `sqlite3` 库

```python
import sqlite3
conn = sqlite3.connect('MSG0_decrypted.db')
cursor = conn.execute('SELECT * FROM messages LIMIT 10')
for row in cursor:
    print(row)
```

### Q: 图片解密后格式不对？

A: 确认：
1. XOR 密钥是否正确（可使用 `detect` 命令自动检测）
2. V4 版本是否需要提供 AES 密钥
3. 输出文件扩展名是否正确（.jpg, .png 等）

### Q: 性能如何？

A: Python 版本性能对比：
- 数据库解密：约 10-20 MB/s（Go 版本：50 MB/s）
- 图片解密：几乎无差异（文件较小）
- 对于普通使用（几百 MB 的数据库）完全够用

## 代码对照表

| 功能 | Go 代码位置 | Python 代码位置 |
|------|------------|----------------|
| V4 解密器 | `go_decrypt/internal/decrypt/windows/v4.go` | `decrypt_core.py:WeChatDBDecryptor` |
| 密钥派生 | `v4.go:54-64` | `decrypt_core.py:55-83` |
| 页面解密 | `common/common.go:100-138` | `decrypt_core.py:126-180` |
| HMAC 验证 | `common.go:106-120` | `decrypt_core.py:85-124` |
| 图片 V3 解密 | `image_decrypt_core.dart:33-40` | `image_decrypt.py:59-81` |
| 图片 V4 解密 | `image_decrypt_core.dart:42-111` | `image_decrypt.py:83-184` |

## 开发指南

### 运行测试

```bash
# 测试数据库解密核心
python decrypt_core.py MSG0.db output.db 0123...cdef

# 测试图片解密核心
python image_decrypt.py image.dat output.jpg 123

# 测试命令行工具
python wechat_decrypt.py --help
```

### 代码结构

```
python_decrypt/
├── decrypt_core.py      # 数据库解密核心（400+ 行）
├── image_decrypt.py     # 图片解密核心（300+ 行）
├── chat_export.py       # 聊天记录导出核心（400+ 行）
├── wechat_decrypt.py    # 命令行工具（450+ 行）
├── requirements.txt     # 依赖列表
└── README.md           # 本文档
```

### 性能优化

如需更高性能，可以考虑：

```bash
# 使用 PyPy（提升 2-5 倍速度）
pypy3 -m pip install cryptography
pypy3 wechat_decrypt.py db -i input.db -o output.db -k ...

# 使用 Cython 编译核心模块
cythonize -i decrypt_core.py
```

## 许可证

本项目遵循 MIT 许可证。

## 致谢

- 原项目：[EchoTrace](https://github.com/ycccccccy/echotrace)
- 算法参考：Go 解密模块 `go_decrypt/`

## 注意事项

⚠️ **免责声明**：
- 本工具仅用于学习和研究目的
- 请勿用于非法用途
- 请遵守当地法律法规
- 仅解密自己的微信数据

## 更新日志

### v1.1.0 (2024-12-24)

- ✨ **新功能**: 聊天记录导出为 Markdown 格式
  - 支持完整的消息记录导出
  - 自动识别消息类型（文本、图片、语音等）
  - 包含详细的统计信息
  - 格式化时间戳和发送者信息
  - 支持导出数据库结构信息
- 🔧 改进命令行工具，添加 `export` 命令

### v1.0.0 (2024-12-24)

- ✨ 完整实现数据库解密（Windows V4）
- ✨ 完整实现图片解密（V3, V4-V1, V4-V2）
- ✨ 统一命令行接口
- ✨ XOR 密钥自动检测
- ✨ 详细的进度显示和错误提示

## 联系方式

如有问题或建议，请提交 Issue 或 Pull Request。
