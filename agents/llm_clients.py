import os
from dotenv import load_dotenv
from openai import OpenAI
import google.generativeai as genai

load_dotenv()

openai_key = os.getenv("OPENAI_API_KEY")
gemini_key = os.getenv("GEMINI_API_KEY")

if not openai_key:
    raise ValueError("Missing OPENAI_API_KEY")
if not gemini_key:
    raise ValueError("Missing GEMINI_API_KEY")

# Clients
openai_client = OpenAI(api_key=openai_key)
genai.configure(api_key=gemini_key)


def call_chatgpt(prompt):
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content


def call_gemini(prompt):
    # TEMPORARY: route everything to OpenAI
    return call_chatgpt(prompt)