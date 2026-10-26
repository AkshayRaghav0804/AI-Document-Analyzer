"""Claude interaction: direct answers, streaming, and map-reduce for huge inputs."""

from __future__ import annotations

from typing import Callable, Iterator

import anthropic

from . import config

ProgressFn = Callable[[float, str], None]


def estimate_tokens(text: str) -> int:
    return len(text) // 4


def chunk_text(text: str, max_chars: int = config.CHUNK_CHARS, overlap: int = config.CHUNK_OVERLAP) -> list[str]:
    """Split on paragraph boundaries; hard-split any paragraph longer than max_chars."""
    if len(text) <= max_chars:
        return [text]

    pieces: list[str] = []
    for para in text.split("\n\n"):
        while len(para) > max_chars:
            pieces.append(para[:max_chars])
            para = para[max_chars:]
        pieces.append(para)

    chunks, current = [], ""
    for piece in pieces:
        if current and len(current) + len(piece) + 2 > max_chars:
            chunks.append(current)
            current = current[-overlap:] if overlap else ""
        current += piece + "\n\n"
    if current.strip():
        chunks.append(current)
    return chunks


def friendly_error(exc: Exception) -> str:
    if isinstance(exc, anthropic.AuthenticationError):
        return "The API key was rejected. Check it in the sidebar."
    if isinstance(exc, anthropic.PermissionDeniedError):
        return "This API key is not allowed to use the selected model."
    if isinstance(exc, anthropic.NotFoundError):
        return "The selected model was not found. Pick another model in the sidebar."
    if isinstance(exc, anthropic.RateLimitError):
        return "Rate limit reached. Wait a minute and try again, or use a smaller model."
    if isinstance(exc, anthropic.APIConnectionError):
        return "Could not reach the Anthropic API. Check your internet connection."
    if isinstance(exc, anthropic.BadRequestError):
        return f"The request was rejected: {getattr(exc, 'message', exc)}"
    return f"Unexpected error: {exc}"


class Analyzer:
    def __init__(self, api_key: str, model: str):
        # The SDK retries rate limits and transient errors with backoff.
        self.client = anthropic.Anthropic(api_key=api_key, max_retries=5)
        self.model = model

    # ------------------------------------------------------------------ routing
    @staticmethod
    def needs_map_reduce(corpus: str) -> bool:
        return estimate_tokens(corpus) > config.MAX_DIRECT_TOKENS

    def stream_answer(
        self,
        question: str,
        corpus: str,
        history: list[dict] | None = None,
        progress: ProgressFn | None = None,
    ) -> Iterator[str]:
        """Yield the answer text as it is generated."""
        if self.needs_map_reduce(corpus):
            yield from self._map_reduce(question, corpus, progress)
        else:
            yield from self._direct(question, corpus, history or [])

    # ------------------------------------------------------------------- direct
    def _direct(self, question: str, corpus: str, history: list[dict]) -> Iterator[str]:
        past = [{"role": m["role"], "content": m["content"]} for m in history[-config.HISTORY_TURNS:]]
        while past and past[0]["role"] != "user":  # API requires user-first
            past.pop(0)

        system = [
            {"type": "text", "text": config.SYSTEM_PROMPT},
            # Cached: follow-up questions about the same files are cheaper and faster.
            {"type": "text", "text": f"<documents>\n{corpus}\n</documents>", "cache_control": {"type": "ephemeral"}},
        ]
        with self.client.messages.stream(
            model=self.model,
            max_tokens=config.MAX_ANSWER_TOKENS,
            system=system,
            messages=past + [{"role": "user", "content": question}],
        ) as stream:
            yield from stream.text_stream

    # --------------------------------------------------------------- map-reduce
    def _map_reduce(self, question: str, corpus: str, progress: ProgressFn | None) -> Iterator[str]:
        chunks = chunk_text(corpus)
        findings = []
        for i, chunk in enumerate(chunks, 1):
            if progress:
                progress(i / (len(chunks) + 1), f"Reading section {i} of {len(chunks)}")
            reply = self.client.messages.create(
                model=self.model,
                max_tokens=config.MAX_MAP_TOKENS,
                system=config.SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Section {i} of {len(chunks)}.\n\n<section>\n{chunk}\n</section>\n\n"
                        f"Question: {question}\n\n"
                        "Extract only what is relevant to the question: facts, figures, names, dates, "
                        "and the file/page/sheet they come from. If nothing is relevant, reply exactly: NONE"
                    ),
                }],
            )
            text = reply.content[0].text.strip()
            if text.upper() != "NONE":
                findings.append(f"[Section {i}]\n{text}")

        if progress:
            progress(0.95, "Combining findings")
        if not findings:
            yield "I could not find anything relevant to that question in the documents."
            return

        with self.client.messages.stream(
            model=self.model,
            max_tokens=config.MAX_ANSWER_TOKENS,
            system=config.SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    "These notes were extracted from consecutive sections of the documents:\n\n"
                    + "\n\n".join(findings)
                    + f"\n\nUsing only these notes, answer the question: {question}\n"
                    "Merge duplicates and mention section numbers where useful."
                ),
            }],
        ) as stream:
            yield from stream.text_stream
