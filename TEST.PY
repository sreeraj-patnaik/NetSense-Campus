import urllib.request

url = "https://diamond-voted-intake-objects.trycloudflare.com/api/tags"

req = urllib.request.Request(
    url,
    headers={
        "User-Agent": "Python"
    }
)

with urllib.request.urlopen(req, timeout=20) as r:
    print(r.status)
    print(r.read().decode()[:500])