from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
import os
from dotenv import load_dotenv
import asyncio
import nats
import json
import uuid
from loguru import logger

load_dotenv()

app = FastAPI(title="Local AI Coordinator")

nats_client = None


async def get_nats():
    global nats_client
    if nats_client is None or not nats_client.is_connected:
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
        nats_client = await nats.connect(nats_url)
        logger.info(f"✅ Connected to NATS: {nats_url}")
    return nats_client


@app.post("/generate")
async def generate(request: Request):
    data = await request.json()
    request_id = str(uuid.uuid4())

    logger.info(f"[{request_id}] 收到生成请求")

    try:
        nc = await get_nats()

        # 转发给本地 Rust Worker
        reply_subject = f"ai.reply.{request_id}"

        await nc.publish(
            "ai.generate",
            json.dumps(
                {
                    "request_id": request_id,
                    "prompt": data.get("prompt"),
                    "lyrics": data.get("lyrics"),
                    "tags": data.get("tags"),
                    **data,
                }
            ).encode("utf-8"),
        )

        # 等待 Worker 回复（超时 3 分钟）
        msg = await nc.request(reply_subject, b"", timeout=180.0)
        result = json.loads(msg.data.decode("utf-8"))

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"[{request_id}] 处理失败: {e}")
        return JSONResponse(
            status_code=500, content={"status": "error", "message": str(e)}
        )


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=3000, reload=True)
