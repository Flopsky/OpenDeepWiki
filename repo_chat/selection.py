from __future__ import annotations

from typing import List, Dict, Any
import os
import instructor
import google.generativeai as genai

from src.schemas.doc_retriver import get_necesary_files


def llm_select_files(
    candidates: List[Dict[str, Any]],
    system_prompt: str,
    user_prompt_template: str,
    safety_settings: List[Dict[str, Any]],
    default_model_name: str,
    max_files: int,
) -> List[Dict[str, Any]]:
    """
    Rank and select top files using an LLM with the get_necesary_files schema.
    candidates should contain items with {"file_name": str, "file_id": int}.
    """
    if not candidates:
        return []

    # Build prompt by injecting candidates
    filled_user_prompt = user_prompt_template.replace("FILES_HERE", str(candidates))

    model_name = os.getenv("FILE_SELECTION_MODEL", default_model_name) or default_model_name
    client = instructor.from_gemini(
        client=genai.GenerativeModel(model_name=model_name, safety_settings=safety_settings),
        mode=instructor.Mode.GEMINI_JSON,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": filled_user_prompt},
    ]

    completion, raw = client.chat.create_with_completion(
        messages=messages,
        response_model=get_necesary_files({"documentation": candidates}),
        generation_config={
            "temperature": 0.0,
            "top_p": 1,
            "candidate_count": 1,
            "max_output_tokens": 8000,
        },
        max_retries=5,
    )
    result = completion.model_dump() or {}
    selected = result.get("files_list", [])
    # Normalize ids to str for compatibility with downstream code
    normalized = [{"file_name": it.get("file_name"), "file_id": str(it.get("file_id"))} for it in selected]
    return normalized[:max_files]


