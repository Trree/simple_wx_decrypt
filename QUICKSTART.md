# 快速开始指南

## 1分钟上手

### 安装

```bash
cd python_decrypt
pip install -r requirements.txt
```

### 解密数据库

```bash
python wechat_decrypt.py db \
  -i MSG0.db \
  -o MSG0_decrypted.db \
  -k 你的64位十六进制密钥
```

### 解密图片

```bash
python wechat_decrypt.py image \
  -i image.dat \
  -o image.jpg \
  -x 123
```

## 常用命令速查

```bash
# 验证密钥
python wechat_decrypt.py validate -i MSG0.db -k 你的密钥

# 查看文件信息
python wechat_decrypt.py info -i MSG0.db

# 自动检测图片XOR密钥
python wechat_decrypt.py detect -i image.dat

# 查看帮助
python wechat_decrypt.py --help
```

## Python 代码使用

```python
from decrypt_core import WeChatDBDecryptor

# 创建解密器
decryptor = WeChatDBDecryptor()

# 解密数据库
decryptor.decrypt_database(
    input_path='MSG0.db',
    output_path='MSG0_decrypted.db',
    hex_key='你的64位十六进制密钥'
)

# 使用解密后的数据库
import sqlite3
conn = sqlite3.connect('MSG0_decrypted.db')
cursor = conn.execute('SELECT * FROM messages LIMIT 10')
for row in cursor:
    print(row)
```

## 获取密钥

密钥需要从微信进程中提取，可以使用以下工具：

- **SharpWxDump** (推荐)
- **WeChatDecrypt**
- **PC-WeChat-Extractor**

密钥格式：64位十六进制字符串
示例：`0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef`

## 目录结构

```
python_decrypt/
├── decrypt_core.py          # 数据库解密核心
├── image_decrypt.py         # 图片解密核心
├── wechat_decrypt.py        # 命令行工具（主入口）
├── examples.py              # 使用示例
├── requirements.txt         # 依赖列表
├── README.md               # 详细文档
└── QUICKSTART.md           # 本文件
```

## 完整示例

```bash
# 1. 验证密钥是否正确
python wechat_decrypt.py validate \
  -i "C:/Users/YourName/Documents/WeChat Files/wxid_xxx/Msg/MSG0.db" \
  -k 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef

# 2. 解密数据库
python wechat_decrypt.py db \
  -i "C:/Users/YourName/Documents/WeChat Files/wxid_xxx/Msg/MSG0.db" \
  -o MSG0_decrypted.db \
  -k 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef

# 3. 使用 SQLite 查看数据
sqlite3 MSG0_decrypted.db "SELECT * FROM messages LIMIT 10"
```

## 常见问题

**Q: 提示 "密钥错误"？**
- 确保密钥是64位十六进制（32字节）
- 密钥与数据库版本匹配

**Q: 如何查看解密后的数据？**
- 使用 DB Browser for SQLite
- 或 Python 的 sqlite3 模块

**Q: 性能如何？**
- 约 10-20 MB/s
- 100MB 数据库大约需要 5-10 秒

## 需要帮助？

查看详细文档：`README.md`
查看使用示例：`examples.py`
