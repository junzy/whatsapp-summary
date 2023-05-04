import logging
from flask import Flask, request, jsonify
import vonage
import openai
import requests
import sqlite3
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# Configure OpenAI API Key
openai.api_key = "[REDACTED]"

# Initialize Vonage client
vonage_client = vonage.Client(
    key="b14d2682", secret="LV4bOnpbHeTgHLTK")
vonage_whatsapp = vonage.Sms(client=vonage_client)

# Database setup


def init_db():
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  sender TEXT, content TEXT, timestamp DATETIME)''')
    conn.commit()
    conn.close()


init_db()


def store_message(sender, content):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute("INSERT INTO messages (sender, content, timestamp) VALUES (?, ?, ?)",
              (sender, content, datetime.now()))
    conn.commit()
    conn.close()
    logging.info(f"Message stored: {sender} - {content}")


def fetch_messages_since(hours=24):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    timestamp = datetime.now() - timedelta(hours=hours)
    c.execute(
        "SELECT sender, content FROM messages WHERE timestamp >= ?", (timestamp,))
    messages = c.fetchall()
    conn.close()
    return messages


def send_message(text):
    url = "https://messages-sandbox.nexmo.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    auth = ("b14d2682", "LV4bOnpbHeTgHLTK")
    data = {
        "from": "14157386102",
        "to": "4915775649185",
        "message_type": "text",
        "text": text,
        "channel": "whatsapp"
    }

    response = requests.post(url, headers=headers, auth=auth, json=data)
    logging.info(f"send_message Response: {response.json()}")


def generate_summary(text):
    response = openai.Completion.create(
        engine="text-davinci-002",
        prompt=f"Please provide a TL;DR of the following conversation:\n{text}",
        max_tokens=100,
        n=1,
        stop=None,
        temperature=0.7,
    )
    logging.info(f"generate_summary Response: {response}")
    return response.choices[0].text.strip()


@app.route('/webhook', methods=['POST'])
def webhook():

    # Parse incoming message
    logging.info(f"Message received: {request.form}")
    data = request.get_json()
    logging.info(f"Data received: {data}")
    sender = data['from']
    content = data['text']
    message_uuid = request.form.get('message_uuid')
    logging.info(f"Message received: {sender} - {content}")

    # Store message in database
    store_message(sender, content)

    # Check for summary command
    if content.strip().lower() == '/summary':
        messages = fetch_messages_since()
        conversation = '\n'.join([f"{m[0]}: {m[1]}" for m in messages])
        logging.info(f"Conversation: {conversation}")
        summary = generate_summary(conversation)
        response_text = f"Summary of the last 24 hours:\n{summary}"
    else:
        response_text = "Message stored. Send /summary as a direct message to the chatbot to get a TL;DR of the last 24 hours' messages."

    # Send the response message
    send_message(response_text)

    return jsonify(status=200)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
