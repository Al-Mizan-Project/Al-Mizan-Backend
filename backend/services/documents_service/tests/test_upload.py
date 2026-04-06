import requests
import json
import sys

url = "http://localhost:8003/api/documents/"
file_path = "pro.pdf"

try:
    with open(file_path, 'rb') as f:
        files = {'file': (file_path, f, 'application/pdf')}
        data = {'related_type': 'soumission'}
        
        response = requests.post(url, files=files, data=data)
        
        print(f"Status Code: {response.status_code}")
        print("Response JSON:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 201:
            doc_id = response.json().get('id_document')
            print(f"\nSUCCESS! File uploaded with ID: {doc_id}")
            print(f"To test download, run GET http://localhost:8003/api/documents/{doc_id}/")
except Exception as e:
    print(f"Error: {str(e)}")
