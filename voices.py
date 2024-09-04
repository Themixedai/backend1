import requests
from flask import Blueprint, request, jsonify
from config import ELEVENLABS_API_KEY, POCKETBASE_URL
from chat import api_request

voices_bp = Blueprint('voices', __name__)

def get_elevenlabs_voices():
    """
    Fetch voices from Elevenlabs API.

    Returns:
        list: List of dictionaries containing voice information.
    """
    url = "https://api.elevenlabs.io/v1/voices"
    headers = {"xi-api-key": ELEVENLABS_API_KEY}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        voices_data = response.json().get('voices', [])

        return [
            {
                "name": voice['name'],
                "voice_id": voice['voice_id'],
                "preview_url": voice['preview_url']
            }
            for voice in voices_data
        ]
    except requests.RequestException as e:
        print(f"Error fetching voices from Elevenlabs: {e}")
        return []

@voices_bp.route('/get_voices', methods=['GET'])
def get_voices():
    """
    Endpoint to get available voices from Elevenlabs.
    """
    voices = get_elevenlabs_voices()
    if voices:
        return jsonify(voices), 200
    else:
        return jsonify({"error": "Failed to fetch voices"}), 500

@voices_bp.route('/assign_voice', methods=['POST'])
def assign_voice():
    """
    Endpoint to assign or update a voice for a specific chatbot.
    """
    data = request.json
    if not all(key in data for key in ['user_id', 'chatbot_id', 'voice_id', 'token']):
        return jsonify({"error": "Missing required parameters"}), 400

    user_id = data['user_id']
    chatbot_id = data['chatbot_id']
    voice_id = data['voice_id']
    token = data['token']

    try:
        # Check if there's an existing voice assignment
        existing_voice = api_request("GET", f"{POCKETBASE_URL}/collections/user_vioces/records", token, 
                                     params={"filter": f"(user_id='{user_id}' && chatbot_id='{chatbot_id}')"})

        voice_data = {
            "user_id": user_id,
            "chatbot_id": chatbot_id,
            "voice_id": voice_id
        }

        if existing_voice and existing_voice.get('items'):
            # Update existing voice assignment
            voice_record_id = existing_voice['items'][0]['id']
            api_request("PATCH", f"{POCKETBASE_URL}/collections/user_vioces/records/{voice_record_id}", token, json=voice_data)
        else:
            # Create new voice assignment
            api_request("POST", f"{POCKETBASE_URL}/collections/user_vioces/records", token, json=voice_data)

        return jsonify({"message": "Voice created or updated!"}), 200
    except Exception as e:
        print(f"Error assigning voice to chatbot: {e}")
        return jsonify({"error": "Failed to assign voice to chatbot"}), 500