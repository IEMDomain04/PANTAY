from __future__ import annotations

import logging

from google import genai
from google.genai import types

from .config import Settings
from .schemas import HistoryMessage


logger = logging.getLogger("katwiran.gemini")


SYSTEM_INSTRUCTION = """
You are Katwiran, a Philippine legal research assistant.

Your primary job is to answer the user's question—not merely present sources.

Response rules:
1. Begin immediately with a direct, plain-language answer.
2. Do not begin with a disclaimer, warning, or description of your role.
3. Synthesize the retrieved passages into a useful explanation.
4. Cite legal claims inline using [1], [2], and so on.
5. Use only citation numbers that correspond to the supplied sources.
6. Explain the applicable legal principles, possible implications, and practical next steps.
7. If the facts are incomplete, explain what facts would materially affect the answer.
8. If the retrieved evidence is insufficient or conflicting, say exactly what cannot be concluded.
9. Never invent a law, case name, quotation, date, court, or legal conclusion.
10. Do not decide that a person is guilty or liable. Explain what may apply and what must be proven.
11. Sensitive subjects—including abuse, assault, coercion, harassment, or violence—are not by
    themselves reasons to refuse. Provide calm, non-graphic, legally relevant information.
12. For immediate danger, add a short safety recommendation after answering the legal question.
13. Mention that this is general legal information only once, briefly, near the end when relevant.
14. Do not produce a separate bibliography because the interface displays source cards.
15. Match the user's language: English, Filipino, or Taglish.

Recommended structure:
- Direct answer
- Legal basis
- How it may apply
- Practical next steps
- Important limitation, if necessary
"""


class GeminiService:
    def __init__(self, settings: Settings) -> None:
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is missing from the backend environment."
            )

        self.model = settings.gemini_model
        self.client = genai.Client(api_key=settings.gemini_api_key)

    async def answer(
        self,
        question: str,
        history: list[HistoryMessage],
        context: str,
    ) -> str:
        recent_history = "\n".join(
            f"{item.role.upper()}: {item.content}"
            for item in history[-8:]
        ) or "No earlier conversation."

        prompt = f"""
Conversation history:
{recent_history}

Retrieved Philippine legal material:
<retrieved_sources>
{context}
</retrieved_sources>

User's current question:
{question}

Give the user a complete, direct answer supported by the retrieved material.
The source cards will be displayed separately, so do not merely summarize or list them.
"""

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.2,
                max_output_tokens=8_192,
            ),
        )

        if not response.candidates:
            block_reason = getattr(
                getattr(response, "prompt_feedback", None),
                "block_reason",
                "unknown",
            )
            raise RuntimeError(
                f"Gemini returned no answer. Block reason: {block_reason}"
            )

        candidate = response.candidates[0]
        finish_reason = getattr(candidate, "finish_reason", None)
        finish_name = getattr(finish_reason, "value", str(finish_reason))

        logger.info("Gemini finish reason: %s", finish_name)

        answer_text = (response.text or "").strip()

        if finish_name == "SAFETY":
            raise RuntimeError(
                "Gemini stopped the response because of its safety evaluation. "
                "Try asking for non-graphic legal analysis of the issue."
            )

        if finish_name == "MAX_TOKENS":
            raise RuntimeError(
                "Gemini reached its response-token limit before completing the answer."
            )

        if not answer_text:
            raise RuntimeError(
                f"Gemini returned an empty response. Finish reason: {finish_name}"
            )

        return answer_text