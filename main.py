from flask import Flask, request, jsonify
import asyncio
import logging
import os
from login import perform_login

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def get_cors_headers():
    origin = '*'
    if request and 'Origin' in request.headers:
        origin = request.headers['Origin']
    return {
        'Access-Control-Allow-Origin': origin,
        'Access-Control-Allow-Methods': 'POST, GET, OPTIONS, PUT, DELETE',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With, Accept, Origin',
        'Access-Control-Max-Age': '3600',
        'Access-Control-Allow-Credentials': 'true'
    }

@app.after_request
def after_request(response):
    for key, value in get_cors_headers().items():
        response.headers[key] = value
    return response

@app.route('/login', methods=['POST', 'GET', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return '', 204
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
