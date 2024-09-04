import logging
import requests
import urllib.parse
import boto3
from botocore.client import Config
import uuid
from config import *

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def api_request(endpoint, token, filter_condition):
    """Generic function to make API requests."""
    url = f"{POCKETBASE_URL}{endpoint}?filter={urllib.parse.quote(filter_condition)}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get('items', [])
    except requests.RequestException as e:
        logging.error(f"Error with API request: {str(e)}")
        return []

def check_audio_mode(user_id, chatbot_id, token):
    items = api_request("/collections/user_modes/records", token, f"(user_id='{user_id}')&&(chatbot_id='{chatbot_id}')")
    return items[0]['audio_mode'] if items else False

def get_voice_id(user_id, chatbot_id, token):
    items = api_request("/collections/user_vioces/records", token, f"(user_id='{user_id}' && chatbot_id='{chatbot_id}')")
    return items[0]['voice_id'] if items else None

def upload_to_linode(audio_content):
    """Uploads audio content to Linode and returns the file URL."""
    filename = f"{uuid.uuid4()}.mp3"
    s3 = boto3.client('s3',
                      endpoint_url=LINODE_ENDPOINT_URL,
                      aws_access_key_id=LINODE_ACCESS_KEY,
                      aws_secret_access_key=LINODE_SECRET_KEY,
                      config=Config(signature_version='s3v4'))
    try:
        s3.put_object(Bucket=BUCKET_NAME, Key=filename, Body=audio_content)
        return f"https://{BUCKET_NAME}.us-southeast-1.linodeobjects.com/{filename}"
    except Exception as e:
        logging.error(f"Error uploading to Linode: {str(e)}")
        return None

def text_to_speech(text, voice_id):
    """Converts text to speech and uploads the audio to Linode."""
    if not ELEVENLABS_API_KEY:
        logging.error("ELEVENLABS_API_KEY is not set")
        return None

    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    data = {"text": text, "model_id": "eleven_multilingual_v2"}
    try:
        response = requests.post(f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}", headers=headers, json=data)
        response.raise_for_status()

        if response.headers.get('Content-Type') == 'audio/mpeg':
            return upload_to_linode(response.content)
        else:
            logging.error(f"Unexpected response content type: {response.headers.get('Content-Type')}")
            return None
    except requests.RequestException as e:
        logging.error(f"Error converting text to speech: {str(e)}")
        return None