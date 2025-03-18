from fastapi import APIRouter, Request, Response, Depends, HTTPException, BackgroundTasks
import json
import logging
import time
import traceback
from routes.handlers.whatsapp_handler import WhatsAppHandler
from config import WHATSAPP_VERIFY_TOKEN, WHATSAPP_ACCESS_TOKEN

logger = logging.getLogger(__name__)

router = APIRouter()

whatsapp_handler = WhatsAppHandler()

# ====== DIAGNOSTIC TEST ENDPOINT ======
@router.get("/whatsapp-test")
async def test_whatsapp_message():
    """
    Test endpoint to diagnose WhatsApp messaging issues.
    This is a standalone endpoint with minimal dependencies.
    """
    test_time = int(time.time())
    test_phone = "919823623966"  # Hardcoded test number
    
    try:
        # Use the same message sender from the handler for direct testing
        message_sender = whatsapp_handler.message_sender
        
        # Create a test message
        test_message = f"🧪 TEST MESSAGE from /whatsapp-test endpoint. Time: {test_time}"
        
        # Log diagnostic info first
        logger.info(f"[WHATSAPP-TEST] Starting test with number: {test_phone}")
        logger.info(f"[WHATSAPP-TEST] Message sender exists: {message_sender is not None}")
        logger.info(f"[WHATSAPP-TEST] Message sender type: {type(message_sender)}")
        
        if not message_sender:
            return {"status": "error", "message": "Message sender is None"}
        
        # Try to send the message
        result = await message_sender.send_message(
            test_phone,
            test_message,
            message_type="diagnostic_test",
            bypass_deduplication=True
        )
        
        logger.info(f"[WHATSAPP-TEST] Message send result: {result}")
        
        return {
            "status": "success" if result else "failed",
            "send_result": result,
            "message": "Test message sent successfully" if result else "Failed to send test message",
            "timestamp": test_time,
            "to": test_phone
        }
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"[WHATSAPP-TEST] Error: {str(e)}")
        logger.error(f"[WHATSAPP-TEST] Trace: {error_trace}")
        
        return {
            "status": "error",
            "error": str(e),
            "trace": error_trace,
            "timestamp": test_time,
            "to": test_phone
        }

@router.get("/whatsapp-webhook")
async def verify_webhook(request: Request):
    """
    Verify the webhook subscription.
    
    Args:
        request: The request object
        
    Returns:
        The challenge string for verification
    """
    try:
        # Get query parameters
        params = dict(request.query_params)
        
        # Get verification parameters
        mode = params.get("hub.mode")
        token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")
        
        logger.info(f"[WEBHOOK] Verifying webhook - Mode: {mode}, Token: {token}")
        
        # Verify token
        if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
            logger.info("[WEBHOOK] Webhook verified!")
            return Response(content=challenge)
        else:
            logger.error("[WEBHOOK] Webhook verification failed!")
            raise HTTPException(status_code=403, detail="Verification failed")
    except Exception as e:
        logger.error(f"[WEBHOOK] Error in verification: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        
@router.post("/whatsapp-webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handle webhook events from WhatsApp.
    
    Args:
        request: The request object
        background_tasks: The background tasks object
        
    Returns:
        A success response
    """
    start_time = time.time()
    logger.info("[NO_ID] === WhatsApp Webhook Route Started ===")
    logger.info(f"[NO_ID] Processing POST request at {time.time()}")
    
    try:
        # Get raw data
        logger.info("[NO_ID] === Processing POST Request ===")
        logger.info("[NO_ID] Step 1: Getting raw data")
        raw_data = await request.body()
        logger.info(f"[NO_ID] Raw data length: {len(raw_data)} bytes")
        logger.info(f"[NO_ID] Raw data: {raw_data.decode()}")
        
        # Parse JSON
        logger.info("[NO_ID] Step 2: Parsing JSON")
        data = json.loads(raw_data.decode())
        logger.info(f"[NO_ID] Parsed data: {json.dumps(data, indent=2)}")
        
        # Handle the webhook event
        logger.info("[NO_ID] Step 3: Calling WhatsApp handler")
        response, status_code = await whatsapp_handler.handle_webhook(data)
        logger.info(f"[NO_ID] Handler result: {response, status_code}")
        
        # Process in background
        # background_tasks.add_task(whatsapp_handler.handle_webhook, data)
        
        # Return a success response
        return {"status": "success", "message": "Webhook received"}
    except Exception as e:
        logger.error(f"[NO_ID] Error processing webhook: {str(e)}")
        logger.error(f"[NO_ID] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e)) 