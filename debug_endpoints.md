# WhatsApp Bot Debug Endpoints

This document describes the debug endpoints available for troubleshooting the WhatsApp bot.

## Available Endpoints

All debug endpoints are available under the `/debug` prefix.

### 1. Test WhatsApp API

**Endpoint:** `/debug/test-whatsapp-api`  
**Method:** POST  
**Purpose:** Send a message directly to the WhatsApp API and get the complete response details.

**Request Body:**
```json
{
  "recipient_phone": "1234567890",
  "message_text": "Test message"
}
```

**Response:** Detailed information about the request and response, including:
- Request details (URL, headers, payload)
- Response details (status code, headers, body)
- Timing information

**Example Usage:**
```bash
curl -X POST http://your-app-url/debug/test-whatsapp-api \
  -H "Content-Type: application/json" \
  -d '{"recipient_phone": "1234567890", "message_text": "Test message"}'
```

### 2. Test Redis Connection

**Endpoint:** `/debug/test-redis`  
**Method:** GET  
**Purpose:** Test the Redis connection and view WhatsApp-related keys.

**Response:** Information about the Redis connection, including:
- Connection status
- Test operations (ping, set, get)
- List of WhatsApp-related keys in Redis
- Total number of WhatsApp keys

**Example Usage:**
```bash
curl http://your-app-url/debug/test-redis
```

### 3. Test Message Deduplication

**Endpoint:** `/debug/test-message-deduplication`  
**Method:** POST  
**Purpose:** Check if a message would be deduplicated by the system.

**Request Body:**
```json
{
  "message_id": "wamid.123456789",
  "from_number": "1234567890",
  "message_type": "text"
}
```

**Response:** Detailed information about the deduplication check, including:
- Whether the message would be deduplicated
- Message details
- Redis key information
- Existing keys for the phone number

**Example Usage:**
```bash
curl -X POST http://your-app-url/debug/test-message-deduplication \
  -H "Content-Type: application/json" \
  -d '{"message_id": "wamid.123456789", "from_number": "1234567890"}'
```

## Troubleshooting Tips

1. **WhatsApp API Issues:**
   - Use the `/debug/test-whatsapp-api` endpoint to send a test message directly to the API
   - Check the complete response for any error messages
   - Verify that the status code is 200 for successful messages

2. **Redis Deduplication Issues:**
   - Use the `/debug/test-redis` endpoint to verify Redis connection
   - Use the `/debug/test-message-deduplication` endpoint to check if messages are being incorrectly deduplicated
   - Look for keys with the pattern `whatsapp:msg:{phone_number}:{message_id}`

3. **Command Response Issues:**
   - Set the `message_type` parameter to a command type (e.g., "list_command", "help_command", "find_command", "ask_command")
   - Verify that command responses are not being deduplicated (should return `"is_duplicate": false`)

## Security Note

These endpoints are intended for debugging purposes only and should be disabled or protected in production environments. 