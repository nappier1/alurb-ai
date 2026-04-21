from flask import Flask, jsonify, request
from threading import Thread
import logging
import time
import os

app = Flask(__name__)
logger = logging.getLogger(__name__)
start_time = time.time()

@app.route('/')
def home():
    return """
    <html>
    <head>
        <title>Alurb Bot - 24/7 Active</title>
        <style>
            body { font-family: Arial; text-align: center; padding: 50px; 
                   background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
            h1 { font-size: 3em; }
            .status { color: #4ade80; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>🤖 Alurb Bot</h1>
        <p class="status">✅ 24/7 Active & Online</p>
        <p>Telegram Godfather Bot with Alurb AI</p>
        <p>👨‍💻 Creators: Nappier & Ruth</p>
        <p>© alurb_devs</p>
    </body>
    </html>
    """

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy", 
        "bot": "Alurb Bot", 
        "uptime": int(time.time() - start_time),
        "creators": "Nappier & Ruth"
    })

@app.route('/ping')
def ping():
    return "pong", 200

def run():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
    logger.info(f"🌐 Keep-alive server started on port {os.environ.get('PORT', 10000)}")
