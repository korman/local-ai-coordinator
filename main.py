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
from typing import Dict, Optional

load_dotenv()

app = FastAPI(title="Local AI Coordinator - 带进度轮询版", version="0.3.0")


class GenerateRequest(BaseModel):
    prompt: str = "中文流行，情感，男声，钢琴"
    lyrics: str = "夜雨敲打着东京的窗\n霓虹灯下我一个人彷徨"
    tags: str = "chinese pop, emotional, male vocal, piano"
    model_config = ConfigDict(extra="allow")


nats_client = None
status_cache: Dict[str, dict] = {}  # 进度缓存
results_cache: Dict[str, dict] = {}  # 最终结果缓存


async def get_nats():
    global nats_client
    if nats_client is None or not nats_client.is_connected:
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
        nats_client = await nats.connect(nats_url)
        logger.info(f"✅ Connected to NATS: {nats_url}")
    return nats_client


# ================== 后台监听进度 + 结果 ==================
async def listen_nats():
    nc = await get_nats()
    # 监听所有进度
    progress_sub = await nc.subscribe("ai.progress.>")
    # 监听所有最终结果
    result_sub = await nc.subscribe("ai.results.>")

    logger.info("📡 进度与结果监听器已启动")

    async for msg in progress_sub.messages:
        try:
            data = json.loads(msg.data.decode("utf-8"))
            req_id = data.get("request_id")
            if req_id:
                status_cache[req_id] = data
                logger.info(f"📈 收到进度更新 [{req_id}]: {data.get('progress')}%")
        except Exception as e:
            logger.error(f"进度解析失败: {e}")

    async for msg in result_sub.messages:  # 实际会和上面是同一个循环，这里简化演示
        try:
            data = json.loads(msg.data.decode("utf-8"))
            req_id = data.get("request_id")
            if req_id:
                results_cache[req_id] = data
                status_cache[req_id] = {"status": "success", "progress": 100, **data}
                logger.info(f"✅ 收到最终结果 [{req_id}]")
        except Exception as e:
            logger.error(f"结果解析失败: {e}")


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(listen_nats())


@app.post("/generate")
async def generate(req: GenerateRequest):
    request_id = str(uuid.uuid4())
    logger.info(f"[{request_id}] 收到生成请求")

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

        await nc.publish("ai.generate", payload)
        logger.info(f"[{request_id}] 任务已 publish（立即返回）")

        return JSONResponse(
            content={
                "status": "processing",
                "request_id": request_id,
                "message": "任务已提交，正在生成中...",
            }
        )

    except Exception as e:
        logger.error(f"[{request_id}] 提交失败: {e}")
        return JSONResponse(
            status_code=500, content={"status": "error", "message": str(e)}
        )


@app.get("/status/{request_id}")
async def get_status(request_id: str):
    """轮询进度接口"""
    if request_id in results_cache:
        result = results_cache.pop(request_id)
        return JSONResponse(content=result)

    if request_id in status_cache:
        return JSONResponse(content=status_cache[request_id])

    return JSONResponse(
        content={
            "status": "processing",
            "request_id": request_id,
            "progress": 0,
            "message": "等待生成...",
        }
    )


@app.get("/results/{request_id}")
async def get_result(request_id: str):
    """最终结果（成功后调用）"""
    if request_id in results_cache:
        result = results_cache.pop(request_id)
        status_cache.pop(request_id, None)  # 清理
        return JSONResponse(content=result)
    return JSONResponse(
        content={
            "status": "processing",
            "request_id": request_id,
            "message": "还在生成中...",
        }
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=3000, reload=True)
