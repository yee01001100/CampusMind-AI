"""Integration seam used by Agent 3's FastAPI chat endpoint."""

from .facade import AgentChatFacade, build_agent_runtime

__all__ = ["AgentChatFacade", "build_agent_runtime"]
