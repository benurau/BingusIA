import asyncio
import json

from bingus_ia.core.agent import Agent
from bingus_ia.core.config import load_config

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

app = FastAPI(title="Bingus IA API") if FASTAPI_AVAILABLE else None
_agent: Agent | None = None


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        config = load_config()
        _agent = Agent(config)
    return _agent


if FASTAPI_AVAILABLE:

    class ChatRequest(BaseModel):
        prompt: str

    class ChatResponse(BaseModel):
        response: str

    @app.on_event("startup")
    async def startup():
        get_agent()

    @app.on_event("shutdown")
    async def shutdown():
        if _agent:
            await _agent.close()

    @app.post("/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest):
        agent = get_agent()
        try:
            result = await agent.run(req.prompt)
            return ChatResponse(response=result)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/health")
    async def health():
        return {"status": "ok", "model": get_agent().config.model}

    @app.post("/injections/reload")
    async def reload_injections():
        agent = get_agent()
        count = agent.injections.reload()
        return {"reloaded": count}

    @app.get("/injections")
    async def list_injections():
        agent = get_agent()
        return {"injections": [
            {"name": i.name, "enabled": i.enabled, "trigger": i.trigger_phrase, "priority": i.priority}
            for i in agent.injections.injections
        ]}
