import json
import urllib.request
import urllib.error

base_url = "http://localhost:8000"

def login():
    url = f"{base_url}/auth/login"
    data = json.dumps({
        "email": "admin@example.com",
        "password": "new_password"
    }).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data.get("access")
    except Exception as e:
        return None

token = login()

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

url = f"{base_url}/attributions-provisoires/1/"
req = urllib.request.Request(url, headers=headers, method="GET")

try:
    with urllib.request.urlopen(req, timeout=5) as response:
        print(f"SUCCESS (200)")
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}")
    body = e.read().decode("utf-8")
    # if it's html (Django debug), let's look for exception_value
    if "Exception Value:" in body:
        start = body.find("Exception Value:")
        print(body[start:start+500])
    else:
        print(body[:500])
except Exception as e:
    print(f"ERREUR: {e}")
