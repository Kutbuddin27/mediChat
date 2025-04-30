import requests
import os
from dotenv import load_dotenv
load_dotenv()

url = "https://api.gupshup.io/wa/api/v1/msg"

payload = {
    "message": "{\"type\":\"quick_reply\",\"msgid\":\"qr1\",\"content\":{\"type\":\"text\",\"header\":\"Okay! We have the following doctors available:\",\"text\":\"Please select a doctor by typing the corresponding letter.\"},\"options\":[{\"type\":\"text\",\"title\":\"Dr. Batra\"},{\"type\":\"text\",\"title\":\"Dr. shah\"},{\"type\":\"text\",\"title\":\"Dr. Momin\"}]}",
    "channel": "whatsapp",
    "source": os.getenv("gupshup_source"),
    "destination": "9",
    "src.name": os.getenv("gupshup_app_name")
}
headers = {
    "accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded",
    "apikey": os.getenv("gupshup_api_key")
}

response = requests.post(url, data=payload, headers=headers)

print(response.text)