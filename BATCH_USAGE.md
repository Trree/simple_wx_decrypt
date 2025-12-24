# 批量解密使用指南

本文档介绍如何使用批量解密功能，按照 EchoTrace 项目的思路，批量处理微信数据库文件。

## 核心特性

✨ **与 EchoTrace 相同的处理方式**
- 每个 `.db` 文件单独解密为对应的 `.db` 文件
- 保持原有目录结构（如 `Msg/message_0.db` → `output/Msg/message_0.db`）
- 不会合并成单个数据库
- 后续可以使用数据库工具分别查询或合并查询

## 快速开始

### 1. 基本用法

```bash
python wechat_decrypt.py batch \
  -i "C:/Users/YourName/Documents/WeChat Files/wxid_abc123" \
  -o ./decrypted \
  -k 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
```

### 2. 先扫描再解密（推荐）

```bash
# 第一步：仅扫描，查看有哪些数据库
python wechat_decrypt.py batch \
  -i "C:/WeChat Files/wxid_xxx" \
  -o ./output \
  -k YOUR_KEY \
  --scan-only

# 第二步：确认无误后开始解密
python wechat_decrypt.py batch \
  -i "C:/WeChat Files/wxid_xxx" \
  -o ./output \
  -k YOUR_KEY
```

### 3. 并行解密（推荐，提速 3-4 倍）

```bash
python wechat_decrypt.py batch \
  -i "C:/WeChat Files/wxid_xxx" \
  -o ./decrypted \
  -k YOUR_KEY \
  --parallel 4
```

## 目录结构示例

### 典型的微信账号目录

```
C:/Users/YourName/Documents/WeChat Files/wxid_abc123/
├── Msg/
│   ├── message_0.db      # 消息数据库分片 0
│   ├── message_1.db      # 消息数据库分片 1
│   ├── message_2.db      # 消息数据库分片 2
│   ├── session.db        # 会话列表数据库
│   └── contact.db        # 联系人数据库
├── Media/
│   └── media_0.db        # 媒体数据库
└── ...其他文件
```

### 解密后的输出目录

```
./decrypted/
├── Msg/
│   ├── message_0.db      # 解密后的消息数据库 0
│   ├── message_1.db      # 解密后的消息数据库 1
│   ├── message_2.db      # 解密后的消息数据库 2
│   ├── session.db        # 解密后的会话列表
│   └── contact.db        # 解密后的联系人
└── Media/
    └── media_0.db        # 解密后的媒体数据库
```

## 核心设计思路（与 EchoTrace 一致）

### 为什么不合并数据库？

1. **保持原始结构**：微信使用分片数据库（message_0.db, message_1.db 等），保持这种结构便于理解和管理
2. **按需加载**：可以选择性地只打开需要的数据库，节省内存
3. **并行处理**：多个数据库可以并行解密，提高效率
4. **灵活查询**：后续可以使用程序跨多个数据库查询（如 EchoTrace 的 `_collectTableInfosAcrossDatabases` 方法）

### 如何使用解密后的数据库？

#### 方法 1：使用 SQLite 工具单独查看

```bash
# 使用 DB Browser for SQLite 打开单个数据库
DB_Browser_for_SQLite message_0.db

# 或使用 sqlite3 命令行
sqlite3 message_0.db
```

#### 方法 2：使用 Python 脚本合并查询

```python
import sqlite3
from pathlib import Path

# 打开多个数据库
dbs = []
for i in range(3):  # message_0.db, message_1.db, message_2.db
    db_path = f"./decrypted/Msg/message_{i}.db"
    if Path(db_path).exists():
        conn = sqlite3.connect(db_path)
        dbs.append(conn)

# 从所有数据库查询并合并结果
all_messages = []
for db in dbs:
    cursor = db.execute("SELECT * FROM Message LIMIT 100")
    all_messages.extend(cursor.fetchall())

# 按时间排序
all_messages.sort(key=lambda x: x[2], reverse=True)  # 假设第3列是时间戳

print(f"总共找到 {len(all_messages)} 条消息")
```

#### 方法 3：使用 ATTACH DATABASE（推荐）

```python
import sqlite3

# 主数据库
main_conn = sqlite3.connect("./decrypted/Msg/message_0.db")

# 附加其他数据库
main_conn.execute("ATTACH DATABASE './decrypted/Msg/message_1.db' AS db1")
main_conn.execute("ATTACH DATABASE './decrypted/Msg/message_2.db' AS db2")

# 跨数据库查询
query = """
SELECT * FROM Message
UNION ALL
SELECT * FROM db1.Message
UNION ALL
SELECT * FROM db2.Message
ORDER BY create_time DESC
LIMIT 100
"""

cursor = main_conn.execute(query)
for row in cursor:
    print(row)
```

## 参数详解

### 必需参数

- `-i, --input`: 输入根目录（微信账号目录，如 `C:/WeChat Files/wxid_xxx`）
- `-o, --output`: 输出根目录（解密后的文件存放位置）
- `-k, --key`: 64 位十六进制密钥（32 字节）

### 可选参数

- `--parallel N`: 并行线程数
  - `0`: 顺序解密（默认，显示详细进度）
  - `1-8`: 并行解密（推荐 4）
  - 注意：并行数过多可能导致磁盘 I/O 瓶颈

- `--skip-validation`: 跳过密钥验证
  - ⚠️ 不推荐，可能导致解密失败
  - 仅在确定密钥正确时使用

- `--scan-only`: 仅扫描文件，不解密
  - 用于预览有哪些数据库需要解密
  - 查看总大小和文件列表

- `-q, --quiet`: 安静模式
  - 减少输出信息
  - 适合脚本自动化使用

## 性能建议

### 顺序解密 vs 并行解密

**顺序解密**（`--parallel 0`，默认）：
- ✅ 显示详细的单文件进度
- ✅ 磁盘 I/O 压力小
- ❌ 速度较慢

**并行解密**（`--parallel 4`）：
- ✅ 速度提升 3-4 倍
- ✅ 充分利用多核 CPU
- ❌ 磁盘 I/O 压力大
- ❌ 不显示单文件进度

### 推荐配置

- **小文件（总计 < 500MB）**: 使用顺序解密
- **中等文件（500MB - 2GB）**: 使用 `--parallel 4`
- **大文件（> 2GB）**: 使用 `--parallel 4` 或 `--parallel 8`
- **SSD 硬盘**: 可以使用更高的并行数
- **HDD 机械硬盘**: 建议 `--parallel 2` 或顺序解密

## 常见问题

### Q: 解密后的数据库可以直接打开吗？

A: 可以！解密后是标准的 SQLite 数据库，可以使用任何 SQLite 工具打开。

### Q: 为什么有多个 message_*.db？

A: 微信使用分片数据库来分散数据，每个分片通常对应不同的会话或时间段。这是正常的。

### Q: 如何查询所有消息？

A: 参考上面的「方法 3：使用 ATTACH DATABASE」，可以一次性查询多个数据库。

### Q: 密钥验证很慢，可以跳过吗？

A: 可以使用 `--skip-validation` 跳过，但不推荐。如果密钥错误，解密会失败并浪费时间。

### Q: 并行解密会不会出错？

A: 不会。每个数据库独立解密，互不影响。并行只是同时处理多个文件。

### Q: 解密失败了怎么办？

A: 检查：
1. 密钥是否正确（使用 `validate` 命令验证）
2. 数据库文件是否损坏
3. 磁盘空间是否充足
4. 输出目录权限是否正确

### Q: 可以只解密部分数据库吗？

A: 可以。将需要解密的数据库放到单独的目录，然后指定该目录作为输入。

## 高级用法

### 1. 批处理脚本（Windows）

创建 `batch_decrypt.bat`：

```batch
@echo off
set INPUT_DIR=C:\Users\YourName\Documents\WeChat Files\wxid_abc123
set OUTPUT_DIR=D:\Decrypted\WeChat
set KEY=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef

python wechat_decrypt.py batch ^
  -i "%INPUT_DIR%" ^
  -o "%OUTPUT_DIR%" ^
  -k %KEY% ^
  --parallel 4

pause
```

### 2. 批处理脚本（Linux/Mac）

创建 `batch_decrypt.sh`：

```bash
#!/bin/bash

INPUT_DIR="/home/user/WeChat Files/wxid_abc123"
OUTPUT_DIR="/home/user/decrypted"
KEY="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

python3 wechat_decrypt.py batch \
  -i "$INPUT_DIR" \
  -o "$OUTPUT_DIR" \
  -k "$KEY" \
  --parallel 4

echo "解密完成！"
```

### 3. Python 脚本调用

```python
from batch_decrypt import BatchDecryptor

# 创建批量解密器
decryptor = BatchDecryptor(
    key="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    skip_validation=False
)

# 扫描数据库
db_files = decryptor.scan_databases("C:/WeChat Files/wxid_xxx")
print(f"找到 {len(db_files)} 个数据库")

# 批量解密
success, failed = decryptor.decrypt_batch(
    root_dir="C:/WeChat Files/wxid_xxx",
    output_dir="./decrypted",
    max_workers=4
)

print(f"成功: {len(success)}, 失败: {len(failed)}")
```

## 总结

批量解密功能完全按照 EchoTrace 的思路设计：
- ✅ 每个数据库独立解密
- ✅ 保持原有目录结构
- ✅ 支持并行处理
- ✅ 灵活的后续查询方式

这种设计既保持了数据的原始结构，又提供了灵活的处理方式，非常适合处理微信的分片数据库。
