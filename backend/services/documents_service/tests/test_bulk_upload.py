import requests
import json
import sys

url = "http://localhost:8003/api/documents/"
file_path_1 = r"d:\almizan\services\documents\dummy1.txt"
file_path_2 = r"d:\almizan\services\documents\dummy2.txt"

try:
    with open(file_path_1, 'rb') as f1, open(file_path_2, 'rb') as f2:
        # Pass multiple files in the same fields
        files = [
            ('files', ('dummy1.txt', f1, 'text/plain')),
            ('files', ('dummy2.txt', f2, 'text/plain'))
        ]
        data = {'related_type': 'soumission'}
        
        response = requests.post(url, files=files, data=data)
        
        print(f"Status Code: {response.status_code}")
        print("Response JSON:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 201:
            print("\nSUCCESS! Bulk files uploaded.")
except Exception as e:
    print(f"Error: {str(e)}")
