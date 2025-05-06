import requests


response = requests.post(url, data=payload, headers=headers)

print(response.text)