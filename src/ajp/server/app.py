"""FastAPI application for AJP REST API server."""

import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    AsyncJournalService,
    BackpressureInfo,
    HealthStatus,
    JournalEntryCreate,
    JournalEntryResponse,
    ServerStats,
    create_entry,
    flush_buffer,
    get_agents,
    get_backpressure,
    get_service,
    get_stats,
    health_check,
    read_entries,
    shutdown_service,
    verify_chain,
    AgentInfo,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ajp.server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage server lifecycle."""
    logger.info("AJP Server starting up...")
    await get_service()
    yield
    await shutdown_service()
    logger.info("AJP Server shut down")


app = FastAPI(
    title="AJP Agent Journal Protocol",
    description="REST API for tamper-evident agent journal logging",
    version="0.5.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthStatus)
async def health():
    """Health check endpoint."""
    return await health_check()


@app.post("/entries", response_model=JournalEntryResponse, status_code=201)
async def post_entry(entry: JournalEntryCreate):
    """Create a new journal entry."""
    try:
        return await create_entry(entry)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/entries", response_model=list[JournalEntryResponse])
async def get_entries(
    agent_id: str = Query(None, description="Filter by agent ID"),
    event_type: str = Query(None, description="Filter by event type"),
    limit: int = Query(100, ge=1, le=1000, description="Max entries to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """Read journal entries."""
    try:
        return await read_entries(agent_id=agent_id, event_type=event_type, limit=limit, offset=offset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats", response_model=ServerStats)
async def stats():
    """Get server statistics."""
    return await get_stats()


@app.get("/agents", response_model=list[AgentInfo])
async def agents():
    """Get list of known agents."""
    return await get_agents()


@app.get("/backpressure", response_model=BackpressureInfo)
async def backpressure():
    """Get backpressure status."""
    return await get_backpressure()


@app.post("/flush")
async def flush():
    """Manually flush the write buffer."""
    return await flush_buffer()


@app.post("/verify/{agent_id}")
async def verify(agent_id: str):
    """Verify chain integrity for an agent."""
    return await verify_chain(agent_id)


def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Run the AJP server."""
    uvicorn.run(
        "ajp.server.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    run_server()
