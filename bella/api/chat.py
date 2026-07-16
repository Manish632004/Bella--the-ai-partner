"""
BELLA - Chat API Routes
REST and streaming endpoints for the chat interface.
"""

import json
import uuid
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from bella.core.llm import llm
from bella.core.conversation import conversation_manager


router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    """Incoming chat message from the client."""
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, description="Session ID for conversation continuity")
    stream: bool = Field(default=True, description="Whether to stream the response")


class ChatResponse(BaseModel):
    """Non-streaming chat response."""
    response: str
    session_id: str


class ClearRequest(BaseModel):
    """Request to clear chat history."""
    session_id: str = Field(..., description="Session ID to clear")


@router.post("/chat")
async def chat(req: ChatRequest):
    """
    Main chat endpoint.
    
    - If stream=True (default): returns SSE stream of tokens
    - If stream=False: returns full response as JSON
    """
    session_id = req.session_id or str(uuid.uuid4())
    conversation = conversation_manager.get_or_create(session_id)
    messages = conversation.add_user_message(req.message)

    if req.stream:
        return StreamingResponse(
            _stream_response(messages, conversation, session_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Session-Id": session_id,
            },
        )
    else:
        response_text = await llm.chat(messages, stream=False)
        conversation.add_assistant_message(response_text)
        return ChatResponse(response=response_text, session_id=session_id)


async def _stream_response(messages: list[dict], conversation, session_id: str):
    """Generator that streams SSE events with individual tokens."""
    full_response = []

    # Send session ID as the first event
    yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"

    try:
        async for token in llm.chat_stream(messages):
            full_response.append(token)
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        # Record full response in conversation history
        complete_text = "".join(full_response)
        conversation.add_assistant_message(complete_text)

        # Send done signal
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"


@router.post("/chat/clear")
async def clear_chat(req: ClearRequest):
    """Clear conversation history for a session."""
    session_id = req.session_id
    if session_id:
        conversation_manager.delete(session_id)
        return {"status": "cleared", "session_id": session_id}
    return {"status": "error", "detail": "No session_id provided"}


@router.get("/health")
async def health_check():
    """Check if Ollama and the model are available."""
    ollama_ok = await llm.check_health()
    return {
        "status": "ok" if ollama_ok else "degraded",
        "ollama": ollama_ok,
        "model": llm.model,
    }
