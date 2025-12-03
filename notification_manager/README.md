# 🚀 智能通知管理中台

> 企业级通知管理平台，支持飞书、钉钉、Flomo等多平台统一管理

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com)
[![Redis](https://img.shields.io/badge/Redis-Enabled-red.svg)](https://redis.io)

## ✨ 特性

- 🎨 **多平台支持** - 飞书、钉钉、Flomo一站式管理
- ⚡ **Redis缓存** - 50倍性能提升
- 🔑 **Token认证** - 企业级API安全
- 📊 **数据统计** - 实时发送状态追踪
- 📝 **消息模板** - 可复用的模板系统
- 🎯 **现代界面** - Bootstrap 5响应式设计

## 🚀 快速开始

```bash
# 安装
pip install -r requirements.txt

# 运行
python app.py

# 访问
http://localhost:5555
```

## 📡 API示例

```bash
# 发送消息
curl -X POST http://localhost:5555/api/send \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello 🚀"}'
```

## 📖 文档

详细文档请查看 [docs/GUIDE.md](docs/GUIDE.md)

## 🆚 vs Server酱

| 功能 | Server酱 | 本系统 |
|------|---------|--------|
| 平台数量 | 1个 | 3个+ |
| 消息模板 | ❌ | ✅ |
| Redis缓存 | ❌ | ✅ |
| 数据统计 | ❌ | ✅ |

## 📁 项目结构

```
├── app.py           # 主应用
├── config.py        # 配置
├── templates/       # 页面模板
├── docs/            # 文档
└── requirements.txt # 依赖
```

## 📄 许可证

MIT License
