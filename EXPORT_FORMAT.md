# JSON 导出格式说明

本文档说明了修改后的 JSON 导出格式，与 EchoTrace 项目保持一致。

## 完整 JSON 结构

```json
{
  "session": {
    "wxid": "string",           // 会话的微信ID
    "nickname": "string",       // 昵称
    "remark": "string",         // 备注
    "alias": "string",          // 别名
    "displayName": "string",    // 显示名称（优先级：备注 > 昵称 > wxid）
    "messageCount": 0           // 消息总数
  },
  "messages": [
    {
      "localId": 0,             // 本地消息ID
      "createTime": 0,          // 创建时间戳（秒）
      "formattedTime": "YYYY-MM-DD HH:MM:SS",  // 格式化时间
      "type": "string",         // 消息类型描述（如"文本消息"、"图片消息"）
      "localType": 0,           // 消息类型代码
      "content": "string",      // 消息内容
      "isSend": 0,              // 是否为发送的消息（0=接收，1=发送）
      "senderUsername": null,   // 发送者的 wxid（群聊中有值，私聊为 null）
      "senderDisplayName": "string",  // 发送者的显示名称
      "senderAvatarKey": null,  // 发送者的头像键（与 senderUsername 相同）
      "source": "string"        // 消息来源（XML 格式）
    }
  ],
  "exportTime": "ISO8601"       // 导出时间（ISO 8601 格式）
}
```

## 与 EchoTrace 的主要差异

### 相同点
- 消息对象的字段完全一致
- 使用相同的消息类型代码和描述
- Session 信息结构相同
- exportTime 格式相同

### 差异点
1. **Session 字段**：
   - EchoTrace 额外包含：`type`（会话类型）、`lastTimestamp`（最后消息时间）
   - simple_wx_decrypt 包含：`alias`（别名）

2. **Avatars**：
   - EchoTrace 包含头像数据（base64 编码）
   - simple_wx_decrypt 不包含头像数据

## 消息类型映射

| 类型代码 | 类型描述 |
|---------|---------|
| 1 | 文本消息 |
| 3 | 图片消息 |
| 34 | 语音消息 |
| 42 | 名片消息 |
| 43 | 视频消息 |
| 47 | 动画表情 |
| 48 | 位置消息 |
| 49 | 链接/文件/引用消息 |
| 50 | 通话消息 |
| 10000 | 系统消息 |
| 10002 | 撤回消息 |
| 244813135921 | 引用消息 |
| 17179869233 | 卡片式链接 |
| 21474836529 | 图文消息 |
| 154618822705 | 小程序分享 |
| 12884901937 | 音乐卡片 |
| 8594229559345 | 红包卡片 |
| 81604378673 | 聊天记录合并转发 |
| 266287972401 | 拍一拍消息 |
| 8589934592049 | 转账卡片 |
| 270582939697 | 视频号直播卡片 |
| 25769803825 | 文件消息 |
| 34359738417 | 文件消息 |
| 103079215153 | 文件消息 |

## 示例输出

### 群聊消息示例

```json
{
  "session": {
    "wxid": "52025729250@chatroom",
    "nickname": "共同富裕",
    "remark": "",
    "alias": "",
    "displayName": "共同富裕",
    "messageCount": 244
  },
  "messages": [
    {
      "localId": 32,
      "createTime": 1766480176,
      "formattedTime": "2025-12-23 16:56:16",
      "type": "引用消息",
      "localType": 244813135921,
      "content": "去抖音直接开直播啊",
      "isSend": 0,
      "senderUsername": "SunnyUIBE",
      "senderDisplayName": "Sunny",
      "senderAvatarKey": "SunnyUIBE",
      "source": "<msgsource>...</msgsource>"
    }
  ],
  "exportTime": "2025-12-24T10:30:45.123456"
}
```

### 私聊消息示例

```json
{
  "session": {
    "wxid": "user_wxid_123",
    "nickname": "张三",
    "remark": "好友备注",
    "alias": "zhangsan",
    "displayName": "好友备注",
    "messageCount": 150
  },
  "messages": [
    {
      "localId": 15,
      "createTime": 1766480200,
      "formattedTime": "2025-12-23 16:56:40",
      "type": "文本消息",
      "localType": 1,
      "content": "你好",
      "isSend": 0,
      "senderUsername": null,
      "senderDisplayName": "好友备注",
      "senderAvatarKey": null,
      "source": "<msgsource>...</msgsource>"
    }
  ],
  "exportTime": "2025-12-24T10:30:45.123456"
}
```

## 变更历史

### 2025-12-24
- ✅ 调整消息类型描述，将 244813135921 从"富文本/引用消息"改为"引用消息"
- ✅ 添加更多消息类型支持（卡片式链接、小程序分享等）
- ✅ 添加 senderUsername、senderDisplayName、senderAvatarKey 字段
- ✅ 移除消息对象中的 database 和 table 字段
- ✅ 移除 statistics 部分，将 messageCount 添加到 session 中
- ✅ 添加联系人信息缓存以提高性能
- ✅ 优化发送者显示名称的获取逻辑
