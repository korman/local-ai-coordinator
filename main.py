from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict  # ← 关键：新增 ConfigDict
import uvicorn
import os
from dotenv import load_dotenv
import nats
import json
import uuid
from loguru import logger

load_dotenv()

app = FastAPI(title="Local AI Coordinator - 本地测试版", version="0.1.0")


# ================== Pydantic v2 正确写法（关键修复）==================
class GenerateRequest(BaseModel):
    prompt: str = "中文流行，情感，男声，钢琴"
    lyrics: str = "夜雨敲打着东京的窗\n霓虹灯下我一个人彷徨"
    tags: str = "chinese pop, emotional, male vocal, piano"

    # Pydantic v2 正确配置方式
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

        payload = json.dumps(
            {
                "request_id": request_id,
                "prompt": req.prompt,
                "lyrics": req.lyrics,
                "tags": req.tags,
                **req.model_dump(),
            }
        ).encode("utf-8")

        msg = await nc.request("ai.generate", payload, timeout=180.0)
        result = json.loads(msg.data.decode("utf-8"))

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"[{request_id}] 处理失败: {e}")
        return JSONResponse(
            status_code=500, content={"status": "error", "message": str(e)}
        )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=3000, reload=True)
