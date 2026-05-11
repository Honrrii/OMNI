import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(dotenv_path=Path.cwd() / ".env")

client = OpenAI(
    base_url=os.getenv("NVIDIA_BASE_URL"),
    api_key=os.getenv("NVIDIA_API_KEY"),
)

response = client.chat.completions.create(
    model=os.getenv("NVIDIA_MODEL"),
    messages=[
        {
            "role": "system",
            "content": "/no_think"
        },
        {
            "role": "user",
            "content": "Reply with exactly this sentence and nothing else: NVIDIA route online."
        }
    ],
    max_tokens=512,
    temperature=0,
    top_p=1,
    stream=False,
)

choice = response.choices[0]
msg = choice.message

print("finish_reason:", choice.finish_reason)
print("content:", repr(msg.content))

if not msg.content:
    print("No final content returned.")
    print("extra fields:", getattr(msg, "model_extra", {}))
