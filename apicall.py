import os
from dotenv import load_dotenv
from twilio.rest import Client

# Load environment variables
load_dotenv()

# Get values from .env
account_sid = os.getenv("ACCOUNT_SID")
auth_token = os.getenv("AUTH_TOKEN")
twilio_phone = os.getenv("TWILIO_PHONE")
target_phone = os.getenv("TARGET_PHONE")
ngrok_host = os.getenv("NGROK_HOST")  
server_url = f"{ngrok_host}/voice"

# Initialize Twilio client
client = Client(account_sid, auth_token)

# Make call
call = client.calls.create(
    to=target_phone,
    from_=twilio_phone,
    url=server_url
)

print(f"Call initiated. Call SID: {call.sid}")
