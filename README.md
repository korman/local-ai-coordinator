# local-ai-coordinator

**作者：郭浩**

这是一个运行在阿里云服务器上的后端服务，负责接收来自前端网站或移动 App 的 AI 生成请求，并通过 NATS 将任务安全转发给家里的 Rust Worker (`local-ai-worker`) 执行。

---

## 项目作用

由于家用电脑通常处于运营商 CGNAT 网络，无法被公网直接访问，本项目解决了以下核心问题：

- 接收前端 / App 发送的 HTTP 请求（prompt、歌词、风格参数等）
- 通过 NATS 消息队列将任务转发给家里电脑的 `local-ai-worker`
- 等待本地 Worker 调用 ComfyUI 等 AI 模型完成生成
- 将生成的音频等结果返回给前端用户

简单来说，它是**家用高性能显卡算力**与**公网前端服务**之间的**安全桥梁和协调器**。

---

## 主要特点

- 使用 FastAPI 提供清晰的 RESTful API
- 通过 NATS 实现异步任务分发（家里电脑主动连接，无需公网入站）
- 支持任务队列、超时处理、错误重试
- 日志记录和监控
- 易于扩展（未来可支持更多 AI 服务）

---

## 技术栈

- Python 3.11+
- FastAPI（Web 框架）
- nats-py（NATS 客户端）
- Uvicorn（ASGI 服务器）
- Pydantic（数据验证）
- python-dotenv（配置管理）

---

## 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/korman/local-ai-coordinator.git
cd local-ai-coordinator

# 2. 安装依赖（推荐使用 uv）
uv sync

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入正确的 NATS_URL

# 4. 运行服务
uv run uvicorn main:app --host 0.0.0.0 --port 3000 --reload