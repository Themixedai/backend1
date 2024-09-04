from flask import Blueprint, request, jsonify
import logging
import requests
from openai import OpenAI
from config import *
from tts import *

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

chat_bp = Blueprint('chat', __name__)
openai = OpenAI(api_key=DEEPINFRA_API_KEY, base_url=OPENAI_BASE_URL)

def api_request(method, url, token, **kwargs):
    headers = {"Authorization": f"{BEARER} {token}"}
    try:
        response = requests.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"API request error: {e}")
        raise

def get_or_create_conversation(user_id, chatbot_id, token):
    url = f"{POCKETBASE_URL}{CHR}"
    params = {"filter": f"user_id='{user_id}' && chatbot_id='{chatbot_id}'"}
    conversation = api_request("GET", url, token, params=params).get('items', [])

    if conversation:
        return conversation[0]['id']

    conversation_id = api_request("POST", url, token, json={"user_id": user_id, "chatbot_id": chatbot_id})['id']
    chatbot = api_request("GET", f"{POCKETBASE_URL}{CHB}{chatbot_id}", token)
    greeting = chatbot.get("Greeting", "Hello! How can I assist you today?")
    update_conversation_history(conversation_id, user_id, chatbot_id, None, greeting, token)
    return conversation_id

def update_conversation_history(conversation_id, user_id, chatbot_id, user_message, assistant_message, token):
    url = f"{POCKETBASE_URL}{CONVH}"
    messages = [
        {"conversation_id": conversation_id, "user_id": user_id, "chatbot_id": chatbot_id, "message_content": msg, "role": role}
        for msg, role in [(user_message, USER), (assistant_message, ASSISTANT)] if msg
    ]
    for message in messages:
        api_request("POST", url, token, json=message)

def send_request_to_deepinfra(user_id, chatbot_id, user_message, token):
    chatbot = api_request("GET", f"{POCKETBASE_URL}/collections/Chatbots/records/{chatbot_id}", token)
    conversation_id = get_or_create_conversation(user_id, chatbot_id, token)

    history = api_request("GET", f"{POCKETBASE_URL}/collections/conversation_history/records", token, params={
        "filter": f"conversation_id='{conversation_id}'",
        "sort": "created",
        "limit": 60
    }).get('items', [])

    system_prompt = (
        f"Your name is {chatbot['Name']}, description: {chatbot['Description']}, "
        f"personality: {chatbot['Personality']}, setting: {chatbot['Setting']}. "
        f"Example dialogue: {chatbot['Example_dialogue']}."
    )

    messages = [{"role": "system", "content": system_prompt}] + [
        {"role": record["role"], "content": record["message_content"]} for record in history
    ] + [{"role": USER, "content": user_message}]

    chat_completion = openai.chat.completions.create(
        model="cognitivecomputations/dolphin-2.9.1-llama-3-70b",
        messages=messages,
        temperature=0.75,
        max_tokens=3500,
        top_p=0.9
    )

    assistant_message = chat_completion.choices[0].message.content
    update_conversation_history(conversation_id, user_id, chatbot_id, user_message, assistant_message, token)
    return assistant_message

@chat_bp.route('/chat', methods=['POST'])
def chat():
    data = request.json
    try:
        user_id, chatbot_id, user_message, token = data['user_id'], data['chatbot_id'], data['user_message'], data['token']
        response = send_request_to_deepinfra(user_id, chatbot_id, user_message, token)

        if check_audio_mode(user_id, chatbot_id, token):
            voice_id = get_voice_id(user_id, chatbot_id, token)
            if voice_id:
                audio_content = text_to_speech(response, voice_id)
                if audio_content:
                    audio_url = upload_to_linode(audio_content)
                    if audio_url:
                        return jsonify({"assistant_message": response, "audio_url": audio_url}), 200
                    logger.warning("Failed to upload audio, falling back to text-only response")
                else:
                    logger.warning("Failed to generate audio, falling back to text-only response")
            else:
                logger.warning("No voice ID found, falling back to text-only response")

        return jsonify({"assistant_message": response}), 200
    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        return jsonify({"error": str(e)}), 500