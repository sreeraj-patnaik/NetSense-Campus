import os
import json
import urllib.request
import urllib.error

req = urllib.request.Request(
    "https://api.groq.com/openai/v1/chat/completions",
    data=json.dumps({
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": "hello"}]
    }).encode(),
    headers={
        "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
        "Content-Type": "application/json"
    }
)

try:
    with urllib.request.urlopen(req) as r:
        print(r.read().decode())

except urllib.error.HTTPError as e:
    print("STATUS:", e.code)
    print("REASON:", e.reason)

    body = e.read().decode("utf-8", errors="ignore")

    print("\nBODY START\n")
    print(body)
    print("\nBODY END\n")