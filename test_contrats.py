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
    except urllib.error.HTTPError as e:
        print(f"Erreur de login: {e.code} - {e.read().decode('utf-8')}")
        return None
    except Exception as e:
        print(f"Erreur de connexion: {e}")
        return None

token = login()

if not token:
    print("Test interrompu : impossible d'obtenir le token d'authentification.")
    exit(1)

print(f"Authentification réussie. Token obtenu.")
print("-" * 50)

endpoints = [
    ("GET", "/attributions-provisoires/"),
    ("GET", "/attributions-provisoires/1/"),
    ("POST", "/attributions-provisoires/1/affecter/"),
    ("POST", "/attributions-provisoires/1/valider/"),
    ("GET", "/attributions-definitives/"),
    ("GET", "/attributions-definitives/1/"),
]

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Empty JSON for POST requests
post_data = json.dumps({}).encode("utf-8")

for method, path in endpoints:
    url = f"{base_url}{path}"
    req = urllib.request.Request(url, headers=headers, method=method)
    
    if method == "POST":
        # Provide minimal empty body
        req.data = post_data
        
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            print(f"{method} {path: <45} -> SUCCESS (200)")
            # You can print response.read() here if you want to see the JSON
    except urllib.error.HTTPError as e:
        print(f"{method} {path: <45} -> HTTP {e.code}")
    except Exception as e:
        print(f"{method} {path: <45} -> ERREUR: {e}")
