"""
Debug Routes for WhatsApp API Testing
------------------------------------
This module provides debug endpoints for testing the WhatsApp API directly.
These routes should be disabled in production.
"""

import os
import json
import time
import logging
import aiohttp
from flask import Blueprint, request, jsonify

debug_bp = Blueprint('debug', __name__)
logger = logging.getLogger(__name__)

@debug_bp.route('/test-whatsapp-api', methods=['POST'])
async def test_whatsapp_api():
    """
    Test the WhatsApp API directly.
    
    This endpoint allows testing the WhatsApp API without going through the normal
    webhook flow. It sends a message directly to the WhatsApp API and returns the
    complete response.
    
    Request body:
    {
        "to_number": "919823623966",
        "message": "Test message"
    }
    """
    try:
        # Get request data
        data = request.json
        to_number = data.get('to_number')
        message = data.get('message', 'Test message')
        
        if not to_number:
            return jsonify({
                'status': 'error',
                'message': 'Missing to_number parameter'
            }), 400
            
        # Get WhatsApp API credentials
        api_version = os.environ.get('WHATSAPP_API_VERSION', 'v17.0')
        phone_number_id = os.environ.get('WHATSAPP_PHONE_NUMBER_ID')
        access_token = os.environ.get('WHATSAPP_ACCESS_TOKEN')
        
        if not phone_number_id or not access_token:
            return jsonify({
                'status': 'error',
                'message': 'Missing WhatsApp API credentials'
            }), 500
            
        # Add timestamp to make message unique
        timestamp = int(time.time())
        message = f"{message} (Debug Test: {timestamp})"
        
        # Prepare the API request
        url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        
        request_data = {
            'messaging_product': 'whatsapp',
            'to': to_number,
            'type': 'text',
            'text': {'body': message}
        }
        
        # Send the message
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=request_data) as response:
                response_text = await response.text()
                response_headers = dict(response.headers)
                
                # Try to parse the response as JSON
                try:
                    response_json = json.loads(response_text)
                except:
                    response_json = None
                
                # Return the complete response
                return jsonify({
                    'status': 'success',
                    'request': {
                        'url': url,
                        'headers': headers,
                        'data': request_data
                    },
                    'response': {
                        'status': response.status,
                        'headers': response_headers,
                        'body_text': response_text,
                        'body_json': response_json
                    }
                })
                
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }), 500

@debug_bp.route('/test-redis', methods=['GET'])
async def test_redis():
    """
    Test the Redis connection.
    
    This endpoint tests the Redis connection and returns the result.
    """
    try:
        import redis
        import os
        
        redis_url = os.environ.get('REDIS_URL')
        if not redis_url:
            return jsonify({
                'status': 'error',
                'message': 'No Redis URL found in environment variables'
            }), 400
            
        # Connect to Redis
        redis_client = redis.Redis.from_url(
            redis_url,
            socket_timeout=2,
            socket_connect_timeout=2,
            decode_responses=True
        )
        
        # Test the connection
        ping_result = redis_client.ping()
        
        # Set a test value
        test_key = f"debug:test:{int(time.time())}"
        redis_client.set(test_key, "test value", ex=60)
        
        # Get the test value
        test_value = redis_client.get(test_key)
        
        # Get Redis info
        info = redis_client.info()
        
        return jsonify({
            'status': 'success',
            'ping_result': ping_result,
            'test_key': test_key,
            'test_value': test_value,
            'redis_info': {
                'version': info.get('redis_version'),
                'used_memory_human': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients'),
                'uptime_in_seconds': info.get('uptime_in_seconds')
            }
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }), 500

@debug_bp.route('/test-message-deduplication', methods=['POST'])
async def test_message_deduplication():
    """
    Test the message deduplication system.
    
    This endpoint tests the message deduplication system by checking if a message
    would be deduplicated.
    
    Request body:
    {
        "from_number": "919823623966",
        "message_id": "wamid.123456",
        "message_type": "list_command"
    }
    """
    try:
        # Get request data
        data = request.json
        from_number = data.get('from_number')
        message_id = data.get('message_id')
        message_type = data.get('message_type')
        
        if not from_number or not message_id:
            return jsonify({
                'status': 'error',
                'message': 'Missing from_number or message_id parameter'
            }), 400
            
        # Import the deduplication manager
        from routes.handlers.whatsapp.redis_deduplication import RedisDeduplicationManager
        
        # Get Redis URL
        redis_url = os.environ.get('REDIS_URL')
        
        # Create deduplication manager
        dedup = RedisDeduplicationManager(redis_url)
        
        # Check if message would be deduplicated
        is_duplicate = dedup.is_duplicate_message(from_number, message_id, message_type)
        
        return jsonify({
            'status': 'success',
            'is_duplicate': is_duplicate,
            'from_number': from_number,
            'message_id': message_id,
            'message_type': message_type
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }), 500 