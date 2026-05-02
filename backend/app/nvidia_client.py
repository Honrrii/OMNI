import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_MODEL = os.getenv(
    "NVIDIA_MODEL",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5"
)

client = OpenAI(
    api_key=NVIDIA_API_KEY,
    base_url="https://integrate.api.nvidia.com/v1"
)


def ask_nvidia(system_prompt: str, user_prompt: str) -> str:
    if not NVIDIA_API_KEY:
        raise ValueError("NVIDIA_API_KEY is missing. Check your .env file.")

    response = client.chat.completions.create(
        model=NVIDIA_MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        temperature=0.35,
        top_p=0.9,
        max_tokens=2500
    )

    return response.choices[0].message.content