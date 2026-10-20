"""Demo UI for EcoMind AI: chat with the agent and watch Strands Decider 2B decisions in real time.

    ./kit demo            # http://localhost:8501
    DEMO_TARGET=agentcore AGENTCORE_ARN=arn:... ./kit demo     # deployed agent on AWS
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from decider_kit.config import load_dotenv

load_dotenv()
STATIC = Path(__file__).parent / "static"
DATA_DIR = Path(__file__).resolve().parent.parent / "agent" / "data"
app = FastAPI(title="EcoMind AI — Waste Management Decision Agent")
_agent: Any = None


class Turn(BaseModel):
    message: str
    session_id: str = "demo"
    images: list[str] = []


def agent() -> Any:
    global _agent
    if _agent is None:
        if os.environ.get("DEMO_TARGET") == "agentcore":
            _agent = AgentCoreClient(os.environ["AGENTCORE_ARN"])
        else:
            from agent.agent import HackathonAgent
            _agent = HackathonAgent()
    return _agent


class AgentCoreClient:
    """Same chat() interface, served by the deployed agent on Amazon Bedrock AgentCore Runtime."""

    def __init__(self, arn: str):
        import boto3
        self.arn = arn
        self.client = boto3.client("bedrock-agentcore", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        self.sessions: dict[str, str] = {}

    def chat(self, message: str, session_id: str = "demo", images: list[str] | None = None) -> dict[str, Any]:
        sid = self.sessions.setdefault(session_id, f"demo-{session_id}-{uuid.uuid4().hex}")
        payload = {"prompt": message, **({"images": images} if images else {})}
        r = self.client.invoke_agent_runtime(
            agentRuntimeArn=self.arn, runtimeSessionId=sid,
            payload=json.dumps(payload).encode()
        )
        body = r["response"].read() if hasattr(r["response"], "read") else r["response"]
        out = json.loads(body)
        out["served_by"] = "Amazon Bedrock AgentCore Runtime"
        return out


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/info")
def info() -> dict[str, Any]:
    from decider_kit.config import settings
    s = settings()
    name = "EcoMind AI"
    try:
        from agent import agent as mod
        name = getattr(mod, "NAME", name)
    except Exception:
        pass
    decider = s.decider_mode
    if os.environ.get("DEMO_TARGET") == "agentcore":
        dep = Path(__file__).resolve().parent.parent / "submission" / "deployment.json"
        if dep.exists():
            decider = json.loads(dep.read_text()).get("decider_mode", decider)
    from decider_kit.llm import describe
    llm = describe()
    if os.environ.get("DEMO_TARGET") == "agentcore":
        llm = f"Amazon Bedrock ({s.bedrock_model})"
    return {
        "agent": name, "llm": llm, "bedrock_model": s.bedrock_model,
        "decider": decider, "target": os.environ.get("DEMO_TARGET", "local"),
    }


@app.get("/api/bins")
def bins() -> JSONResponse:
    """Return simulated bin records for the demo UI."""
    try:
        with open(DATA_DIR / "bins.json", encoding="utf-8") as f:
            bin_data = json.load(f)
        with open(DATA_DIR / "config.json", encoding="utf-8") as f:
            cfg = json.load(f)
        return JSONResponse({"bins": bin_data, "data_note": cfg.get("data_note", "Simulated data only.")})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/chat")
def chat(t: Turn) -> JSONResponse:
    try:
        a = agent()
        if t.images:
            import inspect
            if "images" not in inspect.signature(a.chat).parameters:
                return JSONResponse(
                    {"error": "this agent does not support images"}, status_code=400
                )
            result = a.chat(t.message, t.session_id, images=t.images)
        else:
            result = a.chat(t.message, t.session_id)

        # Add classification field extracted from first decision record
        classification = None
        if result.get("decisions"):
            d = result["decisions"][0]
            classification = {
                "category": d.get("category", ""),
                "confidence": d.get("confidence", 0.0),
                "low_confidence": d.get("verdict") in ("low_confidence", "fallback"),
            }
        result["classification"] = classification
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)


@app.post("/api/reset")
def reset() -> dict[str, bool]:
    global _agent
    _agent = None
    return {"ok": True}
