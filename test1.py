import requests
import os
from dotenv import load_dotenv
load_dotenv()

def send_welcome_message(phone_number, sender_name):
    whatsapp_api_key = "nggipfjdagd1jrsz70jkzbqot0qgojy7"
    whatsapp_number = "919316576115"
    src_name = 'SamcomDev'
    template_id = '7785cbb7-df0f-4448-a292-040e7d79ee16'

    api_url = 'https://api.gupshup.io/wa/api/v1/template/msg'

    # Validate required data
    if not all([whatsapp_api_key, whatsapp_number, phone_number, sender_name]):
        print("Missing required parameters or environment variables.")
        return False

    # Prepare payload
    payload = {
        'channel': 'whatsapp',
        'source': whatsapp_number,
        'destination': '91' + str(phone_number),
        'src.name': src_name,
        'template': '{"id": "%s", "params": ["%s"]}' % (template_id, sender_name)
    }

    headers = {
        'Cache-Control': 'no-cache',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Apikey': whatsapp_api_key
    }

    # Send request
    try:
        response = requests.post(api_url, data=payload, headers=headers)
        response.raise_for_status()
        print(f"Welcome message sent to {phone_number}: {response.text}")
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return False
send_welcome_message('9725193559', 'John Doe')