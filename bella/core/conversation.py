"""
BELLA - Conversation Manager
Manages conversation history with the system prompt.
Phase 1: simple in-memory list. Phase 4 will add persistent memory.
"""

from bella.core.config import config


class Conversation:
    """
    Manages a single conversation's message history.
    
    The system prompt is always the first message.
    History is kept in memory for now — Phase 4 adds persistence.
    """

    def __init__(self, system_prompt: str | None = None):
        self.system_prompt = system_prompt or config.SYSTEM_PROMPT
        self.messages: list[dict[str, str]] = [
            {"role": "system", "content": self.system_prompt}
        ]

    def add_user_message(self, content: str) -> list[dict[str, str]]:
        """Add a user message and return the full history for the LLM."""
        self.messages.append({"role": "user", "content": content})
        return self.messages

    def add_assistant_message(self, content: str):
        """Record the assistant's response in history."""
        self.messages.append({"role": "assistant", "content": content})

    def get_messages(self) -> list[dict[str, str]]:
        """Return the full message history including system prompt."""
        return self.messages

    def clear(self):
        """Reset conversation, keeping only the system prompt."""
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]

    @property
    def turn_count(self) -> int:
        """Number of user-assistant exchanges."""
        return sum(1 for m in self.messages if m["role"] == "user")


class ConversationManager:
    """
    Manages multiple conversations by session ID.
    Phase 1: in-memory dict. Phase 6 will sync across devices.
    """

    def __init__(self):
        self._sessions: dict[str, Conversation] = {}

    def get_or_create(self, session_id: str) -> Conversation:
        """Get an existing conversation or create a new one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = Conversation()
        return self._sessions[session_id]

    def delete(self, session_id: str):
        """Delete a conversation session."""
        self._sessions.pop(session_id, None)

    def list_sessions(self) -> list[str]:
        """List all active session IDs."""
        return list(self._sessions.keys())


# Module-level singleton
conversation_manager = ConversationManager()
