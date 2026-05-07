import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
import google.generativeai as genai


# Load .env from the project root: AI_Avengers_HQ/.env
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


# API keys / model settings
openai_key = os.getenv("OPENAI_API_KEY")
gemini_key = os.getenv("GEMINI_API_KEY")

nvidia_key = os.getenv("NVIDIA_API_KEY")
nvidia_base_url = os.getenv("NVIDIA_BASE_URL")
nvidia_model = os.getenv("NVIDIA_MODEL")


# Clients
openai_client = OpenAI(api_key=openai_key) if openai_key else None

if gemini_key:
    genai.configure(api_key=gemini_key)

nvidia_client = (
    OpenAI(
        base_url=nvidia_base_url,
        api_key=nvidia_key,
    )
    if nvidia_key and nvidia_base_url
    else None
)


def call_chatgpt(prompt, system_prompt=None):
    """
    OpenAI route.
    Best for structured engineering outputs, artifact synthesis, and validation.
    """
    if not openai_client:
        raise ValueError("Missing OPENAI_API_KEY")

    messages = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    messages.append({"role": "user", "content": prompt})

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,
    )

    return response.choices[0].message.content or ""


def call_gemini(prompt, system_prompt=None):
    """
    Gemini route.
    Best for creative/divergent concept generation and reference synthesis.
    """
    if not gemini_key:
        raise ValueError("Missing GEMINI_API_KEY")

    model = genai.GenerativeModel("gemini-2.5-flash")

    full_prompt = prompt
    if system_prompt:
        full_prompt = f"{system_prompt}\n\n{prompt}"

    response = model.generate_content(full_prompt)

    return response.text or ""


def call_nvidia(
    prompt,
    system_prompt="You are OMNI's engineering reviewer. Be concise, practical, and structured.",
):
    """
    NVIDIA route.
    Best for second-opinion review, risk checks, and engineering critique.
    """
    if not nvidia_client:
        raise ValueError("Missing NVIDIA_API_KEY or NVIDIA_BASE_URL")

    if not nvidia_model:
        raise ValueError("Missing NVIDIA_MODEL")

    response = nvidia_client.chat.completions.create(
        model=nvidia_model,
        messages=[
            {
                "role": "system",
                "content": f"/no_think\n{system_prompt}".strip(),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        max_tokens=1200,
        temperature=0.2,
        top_p=1,
    )

    return response.choices[0].message.content or ""