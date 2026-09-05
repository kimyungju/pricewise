"""Retry malformed model outputs once; never retry graph tool operations."""

from typing import TypeVar

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable
from openai import LengthFinishReasonError
from pydantic import ValidationError

Output = TypeVar("Output")


def recover_output(
    runnable: Runnable[LanguageModelInput, Output],
) -> Runnable[LanguageModelInput, Output]:
    """A second model call may repair invalid JSON or an incomplete schema."""
    return runnable.with_retry(
        retry_if_exception_type=(
            ValidationError,
            OutputParserException,
            LengthFinishReasonError,
        ),
        stop_after_attempt=2,
        wait_exponential_jitter=False,
    )


def require_response(message: BaseMessage) -> AIMessage:
    """A terminal reply needs visible text and cannot request an unexecuted tool."""
    reply = AIMessage.model_validate(message.model_dump())
    if not reply.text.strip() or reply.tool_calls:
        raise OutputParserException(
            "The response model did not produce a final text answer."
        )
    return reply
