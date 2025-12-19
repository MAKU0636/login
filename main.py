from flask import Flask, request, jsonify
import asyncio
import logging
import os
from login import perform_login

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/login', methods=['POST', 'GET'])
def login():
    try:
        result = asyncio.run(perform_login())
        return jsonify(result), 200
    except Exception as e:
        logger.error(f'Error: {str(e)}')
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
