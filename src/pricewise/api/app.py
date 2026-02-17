import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.memory import InMemorySaver

from pricewise.agent import build_agent
from pricewise.api.routes import router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    use_memory = os.getenv("USE_MEMORY_SAVER", "false").lower() == "true"

    try:
        if use_memory:
            logger.info("Starting with InMemorySaver")
            checkpointer = InMemorySaver()
            app.state.agent = build_agent(checkpointer=checkpointer)
            app.state.sessions = {}
            logger.info("Agent ready (in-memory)")
            yield
        else:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            conn_string = os.environ["CHECKPOINT_POSTGRES_URI"]
            logger.info("Connecting to Postgres...")
            async with AsyncPostgresSaver.from_conn_string(conn_string) as checkpointer:
                await checkpointer.setup()
                app.state.agent = build_agent(checkpointer=checkpointer)
                app.state.sessions = {}
                logger.info("Agent ready (postgres)")
                yield
    except Exception:
        logger.exception("Failed during startup")
        raise


def create_app() -> FastAPI:
    load_dotenv()
    app = FastAPI(title="Pricewise API", lifespan=lifespan)

    allowed_origins = [
        o.strip()
        for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    app.include_router(router, prefix="/chat")
    return app
