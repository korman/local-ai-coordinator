from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
import uvicorn
import os
from dotenv import load_dotenv
import nats
import json
import uuid
from loguru import logger
import asyncio

load_dotenv()

app = FastAPI(title="Local AI Coordinator - 本地测试版", version="0.1.0")


class GenerateRequest(BaseModel):
    prompt: str = "中文流行，情感，男声，钢琴"
    lyrics: str = "夜雨敲打着东京的窗\n霓虹灯下我一个人彷徨"
    tags: str = "chinese pop, emotional, male vocal, piano"
    model_config = ConfigDict(extra="allow")


nats_client = None


async def get_nats():
    global nats_client
    if nats_client is None or not nats_client.is_connected:
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
        nats_client = await nats.connect(nats_url)
        logger.info(f"✅ Connected to NATS: {nats_url}")
    return nats_client


@app.post("/generate")
async def generate(req: GenerateRequest):
    request_id = str(uuid.uuid4())
    logger.info(f"[{request_id}] 收到生成请求: prompt={req.prompt[:50]}...")

    try:
        nc = await get_nats()

        # ================== 1. 订阅唯一的结果通道（pub/sub 核心）==================
        result_subject = f"ai.results.{request_id}"
        sub = await nc.subscribe(result_subject, max_msgs=1)

        # ================== 2. 构造 payload 并发布任务 ==================
        payload = json.dumps(
            {
                "request_id": request_id,
                "prompt": req.prompt,
                "lyrics": req.lyrics,
                "tags": req.tags,
                **req.model_dump(),
            }
        ).encode("utf-8")

        await nc.publish("ai.generate", payload)
        logger.info(f"[{request_id}] 任务已 publish 到 ai.generate")

        # ================== 3. 等待结果 ==================
        msg = await sub.next_msg(timeout=180.0)  # 与原来 180 秒一致
        result = json.loads(msg.data.decode("utf-8"))

        await sub.unsubscribe()  # 清理

        return JSONResponse(content=result)

    except asyncio.TimeoutError:
        logger.warning(f"[{request_id}] 超时")
        return JSONResponse(
            status_code=504,
            content={
                "status": "timeout",
                "request_id": request_id,
                "message": "生成超时",
            },
        )
    except Exception as e:
        logger.error(f"[{request_id}] 处理失败: {e}")
        return JSONResponse(
            status_code=500, content={"status": "error", "message": str(e)}
        )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=3000, reload=True)
