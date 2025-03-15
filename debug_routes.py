from flask import Blueprint, request, jsonify
import os
import json
import requests
import redis
from datetime import datetime
import traceback
import logging

# Import necessary components for testing
from config import (
    WHATSAPP_API_VERSION,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_ACCESS_TOKEN
)

# Import Redis deduplication logic
from routes.handlers.whatsapp.message_deduplication import (
    is_duplicate_message,
    get_redis_client
)

# Create blueprint
debug_bp = Blueprint('debug', __name__)
logger = logging.getLogger(__name__)

@debug_bp.route('/test-whatsapp-api', methods=['POST'])
def test_whatsapp_api():
    """
    Test endpoint to send a message directly to WhatsApp API
    and return the complete response.
    
    Expected POST data:
    {
        "recipient_phone": "1234567890",
        "message_text": "Test message"
    }
    """
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        recipient_phone = data.get('recipient_phone')
        message_text = data.get('message_text', 'Test message from debug endpoint')
        
        if not recipient_phone:
            return jsonify({"error": "recipient_phone is required"}), 400
            
        # Format phone number if needed
        if not recipient_phone.startswith('+'):
            recipient_phone = f"+{recipient_phone}"
            
        # Prepare WhatsApp API request
        api_url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
        
        # Add timestamp to make message unique
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        full_message = f"{message_text}\n\nTimestamp: {timestamp}"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "text",
            "text": {
                "body": full_message
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"
        }
        
        # Log the request details
        request_details = {
            "url": api_url,
            "headers": {
                "Content-Type": "application/json",
                "Authorization": "Bearer [REDACTED]"
            },
            "payload": payload
        }
        
        # Make the API request
        start_time = datetime.now()
        response = requests.post(api_url, json=payload, headers=headers)
        end_time = datetime.now()
        
        # Parse response
        try:
            response_json = response.json()
        except:
            response_json = {"error": "Could not parse JSON response"}
            
        # Prepare detailed response
        result = {
            "status": "success" if response.status_code == 200 else "error",
            "request": {
                "url": api_url,
                "payload": payload,
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer [REDACTED]"
                }
            },
            "response": {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response_json,
                "raw_text": response.text
            },
            "timing": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "duration_ms": (end_time - start_time).total_seconds() * 1000
            }
        }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in test-whatsapp-api: {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

@debug_bp.route('/test-redis', methods=['GET'])
def test_redis():
    """Test Redis connection and operations"""
    try:
        redis_url = os.environ.get('REDIS_URL')
        if not redis_url:
            return jsonify({"error": "No Redis URL found in environment variables"}), 500
            
        # Get Redis client
        redis_client = get_redis_client()
        if not redis_client:
            return jsonify({"error": "Failed to get Redis client"}), 500
        
        # Try to ping Redis
        ping_result = redis_client.ping()
        
        # Try to set and get a value
        test_key = "debug_test_connection"
        test_value = f"Connection test at {datetime.now().isoformat()}"
        set_result = redis_client.set(test_key, test_value)
        get_result = redis_client.get(test_key)
        
        # Get all keys with pattern
        all_keys = redis_client.keys("whatsapp:*")
        
        return jsonify({
            "status": "success",
            "redis_url": redis_url.split('@')[1] if '@' in redis_url else "redis://[masked]",
            "ping": ping_result,
            "set": set_result,
            "get": get_result,
            "match": get_result == test_value,
            "whatsapp_keys": all_keys[:100] if len(all_keys) > 100 else all_keys,
            "total_keys": len(all_keys)
        }), 200
    except Exception as e:
        logger.error(f"Error in test-redis: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 500

@debug_bp.route('/test-message-deduplication', methods=['POST'])
def test_message_deduplication():
    """
    Test if a message would be deduplicated
    
    Expected POST data:
    {
        "message_id": "wamid.123456789",
        "from_number": "1234567890",
        "message_type": "optional-message-type"
    }
    """
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        message_id = data.get('message_id')
        from_number = data.get('from_number')
        message_type = data.get('message_type')
        
        if not message_id or not from_number:
            return jsonify({
                "error": "message_id and from_number are required"
            }), 400
            
        # Check if this would be a duplicate
        is_duplicate, details = is_duplicate_message(message_id, from_number, message_type)
        
        # Get Redis client for additional checks
        redis_client = get_redis_client()
        
        # Check if key exists directly
        combined_key = f"whatsapp:msg:{from_number}:{message_id}"
        message_id_key = f"whatsapp:msg:{message_id}"
        
        combined_key_exists = redis_client.exists(combined_key) if redis_client else False
        message_id_exists = redis_client.exists(message_id_key) if redis_client else False
        
        combined_key_value = redis_client.get(combined_key) if redis_client and combined_key_exists else None
        message_id_value = redis_client.get(message_id_key) if redis_client and message_id_exists else None
        
        # Get all keys for this number
        number_keys = redis_client.keys(f"whatsapp:msg:{from_number}:*") if redis_client else []
        
        return jsonify({
            "status": "success",
            "is_duplicate": is_duplicate,
            "message_details": {
                "message_id": message_id,
                "from_number": from_number,
                "message_type": message_type
            },
            "deduplication_details": details,
            "redis_details": {
                "combined_key": combined_key,
                "message_id_key": message_id_key,
                "combined_key_exists": combined_key_exists,
                "message_id_exists": message_id_exists,
                "combined_key_value": combined_key_value,
                "message_id_value": message_id_value,
                "number_keys": number_keys[:20] if len(number_keys) > 20 else number_keys,
                "total_number_keys": len(number_keys)
            }
        })
        
    except Exception as e:
        logger.error(f"Error in test-message-deduplication: {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

def register_debug_routes(app):
    """Register debug routes with the Flask app"""
    app.register_blueprint(debug_bp, url_prefix='/debug')