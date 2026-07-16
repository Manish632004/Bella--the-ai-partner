import pytest
from bella.core.conversation import Conversation, ConversationManager


def test_conversation_initialization():
    system_prompt = "Custom system prompt"
    conv = Conversation(system_prompt=system_prompt)
    assert conv.system_prompt == system_prompt
    assert len(conv.messages) == 1
    assert conv.messages[0] == {"role": "system", "content": system_prompt}


def test_add_messages():
    conv = Conversation()
    initial_len = len(conv.messages)

    # Add user message
    messages = conv.add_user_message("Hello")
    assert len(messages) == initial_len + 1
    assert messages[-1] == {"role": "user", "content": "Hello"}

    # Add assistant message
    conv.add_assistant_message("Hi there")
    assert len(conv.messages) == initial_len + 2
    assert conv.messages[-1] == {"role": "assistant", "content": "Hi there"}
    assert conv.turn_count == 1


def test_clear_conversation():
    conv = Conversation()
    conv.add_user_message("Hello")
    conv.add_assistant_message("Hi there")
    assert len(conv.messages) > 1

    conv.clear()
    assert len(conv.messages) == 1
    assert conv.messages[0]["role"] == "system"


def test_conversation_manager():
    manager = ConversationManager()
    session_id = "test-session"

    # Create new session
    conv1 = manager.get_or_create(session_id)
    assert isinstance(conv1, Conversation)
    assert session_id in manager.list_sessions()

    # Retrieve existing session
    conv2 = manager.get_or_create(session_id)
    assert conv1 is conv2

    # Delete session
    manager.delete(session_id)
    assert session_id not in manager.list_sessions()
