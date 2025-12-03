# 🐳 Docker 使用教程

> 本教程适合零基础用户，手把手教你用 Docker 运行智能通知管理中台

---

## 📋 目录

1. [什么是 Docker？](#什么是-docker)
2. [安装 Docker](#安装-docker)
3. [快速启动（一分钟上手）](#快速启动)
4. [访问系统](#访问系统)
5. [常用命令](#常用命令)
6. [进阶配置](#进阶配置)
7. [常见问题](#常见问题)

---

## 什么是 Docker？

Docker 就像一个**轻量级的虚拟机**，它可以把应用和所有依赖打包在一起，让你不用安装 Python、Redis 等环境，直接一键运行！

**简单理解**：
- 🎁 Docker 镜像 = 打包好的应用（类似安装包）
- 📦 Docker 容器 = 运行中的应用（类似已安装的软件）

---

## 安装 Docker

### Windows 用户

1. 下载 [Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. 双击安装，一路下一步
3. 安装完成后重启电脑
4. 打开 Docker Desktop，等待启动完成（托盘图标变绿）

### Mac 用户

1. 下载 [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)
   - Intel 芯片选择 **Intel Chip**
   - M1/M2/M3/M4 芯片选择 **Apple Chip**
2. 拖动到应用程序文件夹
3. 打开 Docker，等待启动完成

### Linux 用户

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 重新登录后生效
```

### 验证安装

打开终端/命令行，输入：

```bash
docker --version
```

看到版本号就说明安装成功了！🎉

---

## 快速启动

### 方式一：一键启动（推荐新手）

只需要**一行命令**：

```bash
docker run -d --name notification-manager -p 5555:5555 gwozai/notification-manager:latest
```

**命令解释**：
| 参数 | 含义 |
|------|------|
| `docker run` | 运行一个容器 |
| `-d` | 后台运行（不占用终端） |
| `--name notification-manager` | 给容器起个名字 |
| `-p 5555:5555` | 把容器的 5555 端口映射到本机 |
| `gwozai/notification-manager:latest` | 使用的镜像名称 |

### 方式二：使用 Docker Compose（推荐生产环境）

1. 创建一个文件夹，比如 `notification-manager`
2. 在文件夹里创建 `docker-compose.yml` 文件：

```yaml
version: '3.8'

services:
  notification-manager:
    image: gwozai/notification-manager:latest
    container_name: notification-manager
    ports:
      - "5555:5555"
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    volumes:
      - ./data:/app/instance
      - ./logs:/app/logs
    depends_on:
      - redis
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: notification-redis
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  redis_data:
```

3. 在文件夹里运行：

```bash
docker-compose up -d
```

---

## 访问系统

启动成功后，打开浏览器访问：

### 🌐 http://localhost:5555

你会看到这个页面：

```
┌─────────────────────────────────────┐
│     智能通知中台 🚀                  │
│                                     │
│  企业级通知管理平台                  │
│                                     │
│  [免费开始使用]  [了解更多]          │
│                                     │
│  已有账号？立即登录 →                │
└─────────────────────────────────────┘
```

### 第一步：注册账号

1. 点击「免费开始使用」
2. 填写用户名、邮箱、密码
3. 点击「注册」

### 第二步：添加通知平台

1. 登录后进入「添加平台」
2. 选择平台类型（飞书/钉钉/企业微信等）
3. 填写 Webhook URL
4. 点击「添加平台」

### 第三步：获取 API Token

1. 进入「API Token」页面
2. 点击「生成 Token」
3. 复制 Token（注意保密！）

### 第四步：发送通知

```bash
curl -X POST http://localhost:5555/api/send \
  -H "Authorization: Bearer 你的Token" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello World! 🎉"}'
```

---

## 常用命令

### 🟢 启动容器

```bash
docker start notification-manager
```

### 🔴 停止容器

```bash
docker stop notification-manager
```

### 🔄 重启容器

```bash
docker restart notification-manager
```

### 📋 查看运行状态

```bash
docker ps
```

输出示例：
```
CONTAINER ID   IMAGE                              STATUS          PORTS
abc123...      gwozai/notification-manager        Up 2 hours      0.0.0.0:5555->5555/tcp
```

### 📜 查看日志

```bash
# 查看最近 100 行日志
docker logs --tail 100 notification-manager

# 实时查看日志
docker logs -f notification-manager
```

### 🗑️ 删除容器

```bash
# 先停止
docker stop notification-manager

# 再删除
docker rm notification-manager
```

### 🔄 更新到最新版本

```bash
# 1. 停止并删除旧容器
docker stop notification-manager
docker rm notification-manager

# 2. 拉取最新镜像
docker pull gwozai/notification-manager:latest

# 3. 重新启动
docker run -d --name notification-manager -p 5555:5555 gwozai/notification-manager:latest
```

---

## 进阶配置

### 数据持久化

默认情况下，容器删除后数据会丢失。添加 `-v` 参数保存数据：

```bash
docker run -d \
  --name notification-manager \
  -p 5555:5555 \
  -v /你的路径/data:/app/instance \
  -v /你的路径/logs:/app/logs \
  gwozai/notification-manager:latest
```

### 修改端口

如果 5555 端口被占用，可以改成其他端口：

```bash
# 使用 8080 端口
docker run -d --name notification-manager -p 8080:5555 gwozai/notification-manager:latest
```

访问地址变成：http://localhost:8080

### 使用外部 Redis

```bash
docker run -d \
  --name notification-manager \
  -p 5555:5555 \
  -e REDIS_HOST=你的Redis地址 \
  -e REDIS_PORT=6379 \
  -e REDIS_PASSWORD=你的密码 \
  gwozai/notification-manager:latest
```

---

## 常见问题

### ❓ 端口被占用怎么办？

错误信息：`port is already allocated`

**解决方法**：
```bash
# 方法1：停止占用端口的程序
lsof -i :5555  # 查看谁占用了端口
kill -9 进程ID  # 结束该进程

# 方法2：换一个端口
docker run -d --name notification-manager -p 8080:5555 gwozai/notification-manager:latest
```

### ❓ 容器启动失败怎么办？

```bash
# 查看错误日志
docker logs notification-manager
```

### ❓ 如何进入容器内部？

```bash
docker exec -it notification-manager /bin/bash
```

### ❓ 忘记密码怎么办？

目前需要删除数据库重新注册：

```bash
docker exec notification-manager rm /app/instance/notification_manager.db
docker restart notification-manager
```

### ❓ 镜像太大下载慢？

使用国内镜像加速：

```bash
# 编辑 Docker 配置，添加镜像加速器
# Windows/Mac: Docker Desktop -> Settings -> Docker Engine
# 添加:
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn"
  ]
}
```

---

## 🎯 快速参考卡片

```
┌─────────────────────────────────────────────────────────┐
│  📦 智能通知管理中台 - Docker 快速参考                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  🚀 一键启动:                                            │
│  docker run -d --name notification-manager \            │
│    -p 5555:5555 gwozai/notification-manager:latest      │
│                                                         │
│  🌐 访问地址: http://localhost:5555                      │
│                                                         │
│  📋 常用命令:                                            │
│    启动: docker start notification-manager              │
│    停止: docker stop notification-manager               │
│    日志: docker logs notification-manager               │
│    状态: docker ps                                      │
│                                                         │
│  🔄 更新版本:                                            │
│    docker pull gwozai/notification-manager:latest       │
│                                                         │
│  📱 支持平台: 飞书/钉钉/企业微信/Telegram/Flomo/邮件      │
│                                                         │
│  🏷️ 镜像地址:                                            │
│    Docker Hub: gwozai/notification-manager              │
│    GitHub: ghcr.io/gwozai/githubworkflow/notification-manager │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 需要帮助？

- 📖 [完整文档](./GUIDE.md)
- 🐛 [提交问题](https://github.com/gwozai/githubworkflow/issues)
- ⭐ 觉得好用？给个 Star 吧！

---

*最后更新: 2025-12-04*
