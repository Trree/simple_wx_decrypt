# 微信数据解密工具 (Python 版本)

完美复刻 EchoTrace 的 Go 解密核心代码，使用 Python 3.12 实现。

## 特性

✨ **完整功能**
- 🔓 数据库解密 (Windows V4)
- 📁 批量解密（保持目录结构）
- 🖼️ 图片解密 (V3, V4-V1, V4-V2)
- ✅ 密钥验证
- 🔍 XOR 密钥自动检测
- 📊 进度显示
- ⚡ 并行解密支持

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

### 📘 单个数据库解密

解密单个微信加密数据库（MSG0.db、MicroMsg.db 等）：

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

### 📁 批量解密目录（按 EchoTrace 思路）

批量解密整个微信账号目录，保持原有目录结构：

```bash
python wechat_decrypt.py batch -i "C:/WeChat Files/wxid_xxx" -o ./decrypted -k 0123456789abcdef...
```

**特点**：
- ✅ 自动扫描目录下所有 `.db` 文件
- ✅ 保持原有目录结构（如 `message_0.db`、`message_1.db`、`session.db` 等）
- ✅ 批量解密，无需逐个处理
- ✅ 支持并行解密（多线程加速）

**参数说明**：
- `-i, --input`: 输入根目录（微信账号目录）
- `-o, --output`: 输出根目录（解密后的目录结构）
- `-k, --key`: 64 位十六进制密钥
- `--parallel N`: 并行线程数（0=顺序，默认0）
- `--skip-validation`: 跳过密钥验证（不推荐）
- `--scan-only`: 仅扫描文件，不解密
- `-q, --quiet`: 安静模式

**示例**：

```bash
# 基本用法（顺序解密）
python wechat_decrypt.py batch \
  -i "C:/Users/YourName/Documents/WeChat Files/wxid_abc123" \
  -o ./output \
  -k 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef

# 并行解密（4线程，提速 3-4 倍）
python wechat_decrypt.py batch \
  -i "C:/WeChat Files/wxid_xxx" \
  -o ./decrypted \
  -k 0123...cdef \
  --parallel 4

# 仅扫描，不解密
python wechat_decrypt.py batch \
  -i "C:/WeChat Files/wxid_xxx" \
  -o ./output \
  -k 0123...cdef \
  --scan-only

# 安静模式（减少输出）
python wechat_decrypt.py batch \
  -i ./input -o ./output -k 0123...cdef --quiet
```

**输出示例**：

```
======================================================================
微信数据库批量解密
======================================================================

正在扫描目录: C:/WeChat Files/wxid_abc123
----------------------------------------------------------------------
✓ 找到 12 个数据库文件:

    1. Msg\message_0.db
       大小: 234.56 MB
    2. Msg\message_1.db
       大小: 189.23 MB
    3. Msg\message_2.db
       大小: 156.78 MB
    4. Msg\session.db
       大小: 5.12 MB
    5. Msg\contact.db
       大小: 2.34 MB
    ...

总大小: 687.89 MB

======================================================================
开始批量解密
======================================================================
输出目录: ./output
模式: 并行 (4线程)

进度: [12/12] 100.0% | 当前: contact.db

======================================================================
解密完成
======================================================================

总耗时: 1分23秒
成功: 12 个
失败: 0 个

✓ 成功:
  ✓ Msg\message_0.db
    耗时: 18.3秒 | 输出: message_0.db
  ✓ Msg\message_1.db
    耗时: 15.2秒 | 输出: message_1.db
  ...
  总大小: 687.89 MB
```

**目录结构示例**：

输入目录：
```
C:/WeChat Files/wxid_abc123/
├── Msg/
│   ├── message_0.db
│   ├── message_1.db
│   ├── message_2.db
│   ├── session.db
│   └── contact.db
└── Media/
    └── media_0.db
```

输出目录（保持结构）：
```
./output/
├── Msg/
│   ├── message_0.db
│   ├── message_1.db
│   ├── message_2.db
│   ├── session.db
│   └── contact.db
└── Media/
    └── media_0.db
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

## 核心模块

### batch_decrypt.py - 批量解密核心（新增）

**核心类**: `BatchDecryptor`

**主要方法**：

```python
from batch_decrypt import BatchDecryptor

# 创建批量解密器
batch_decryptor = BatchDecryptor(key='hex_key', skip_validation=False)

# 扫描目录
db_files = batch_decryptor.scan_databases('C:/WeChat Files/wxid_xxx')
print(f"找到 {len(db_files)} 个数据库文件")

# 批量解密（顺序）
success_results, failed_results = batch_decryptor.decrypt_batch_sequential(
    root_dir='./input',
    output_dir='./output',
    file_progress_callback=lambda c, t: print(f"{c}/{t}"),
    overall_progress_callback=lambda f, c, t: print(f"[{c}/{t}] {f}")
)

# 批量解密（并行）
success_results, failed_results = batch_decryptor.decrypt_batch(
    root_dir='./input',
    output_dir='./output',
    max_workers=4,
    progress_callback=lambda f, c, t, tf: print(f"{f} {c}/{t}")
)
```

**特性**：
- 🔍 自动扫描目录下所有 `.db` 文件
- 📂 保持原有目录结构
- ⚡ 支持并行解密（ThreadPoolExecutor）
- 📊 详细的进度显示和统计信息
- 🛡️ 错误处理和结果报告

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
simple_wx_decrypt/
├── decrypt_core.py      # 数据库解密核心（435 行）
├── image_decrypt.py     # 图片解密核心（300+ 行）
├── batch_decrypt.py     # 批量解密模块（400+ 行）⭐新增
├── wechat_decrypt.py    # 命令行工具（500+ 行）
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

### v1.1.0 (2025-12-24)

- ✨ **新增批量解密功能**（按 EchoTrace 思路）
- ✨ 支持目录扫描和递归处理
- ✨ 保持原有目录结构
- ✨ 支持并行解密（多线程加速）
- 📊 详细的批量解密进度和统计
- 🛡️ 完善的错误处理和结果报告

### v1.0.0 (2024-12-24)

- ✨ 完整实现数据库解密（Windows V4）
- ✨ 完整实现图片解密（V3, V4-V1, V4-V2）
- ✨ 统一命令行接口
- ✨ XOR 密钥自动检测
- ✨ 详细的进度显示和错误提示

## 联系方式

如有问题或建议，请提交 Issue 或 Pull Request。
