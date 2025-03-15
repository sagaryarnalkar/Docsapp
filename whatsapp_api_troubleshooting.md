# WhatsApp API Troubleshooting Guide

## Latest Changes

We've added two important improvements to help diagnose and fix the WhatsApp message delivery issues:

1. **Detailed API Response Logging**
   - Now logging the complete API response, including headers and body
   - This will help us see exactly what the WhatsApp API is returning

2. **Message Sending Retry Logic**
   - Added automatic retry logic (up to 3 attempts) for sending messages
   - Each attempt is logged with detailed information
   - Short delay between retries to handle temporary issues

## Testing Steps

1. **Deploy the latest changes to your Render server**
   - The changes should be automatically deployed if your Render server is connected to your GitHub repository
   - If not, manually deploy the latest commit from the Render dashboard

2. **Send a test command to the bot**
   - Send a simple command like "list" to the WhatsApp bot
   - Wait a few seconds for the command to be processed

3. **Check the Render logs**
   - Look for the detailed API response logs:
     ```
     [DEBUG] a3f51789 - Response Status: 200
     [DEBUG] a3f51789 - Response Headers: {...}
     [DEBUG] a3f51789 - Response Body: {...}
     ```

## What to Look For

### Successful API Response

A successful API response should look like:
```
[DEBUG] a3f51789 - Response Status: 200
[DEBUG] a3f51789 - Response Body: {"messaging_product":"whatsapp","contacts":[{"input":"919823623966","wa_id":"919823623966"}],"messages":[{"id":"wamid.HBgMOTE5ODIzNjIzOTY2FQIAERgSNTc2QjVDNzM2QTlCNDYyRTk1AA=="}]}
[DEBUG] a3f51789 - Message sent successfully! Message ID: wamid.HBgMOTE5ODIzNjIzOTY2FQIAERgSNTc2QjVDNzM2QTlCNDYyRTk1AA==
```

### Error Response

An error response might look like:
```
[DEBUG] a3f51789 - Response Status: 400
[DEBUG] a3f51789 - Response Body: {"error":{"message":"Error validating access token","type":"OAuthException","code":190}}
```

## Common Issues and Solutions

1. **Rate Limiting**
   - Look for status code 429 or error messages about rate limits
   - Solution: Implement exponential backoff in the retry logic

2. **Message Format Issues**
   - Look for status code 400 with specific error messages about message format
   - Solution: Adjust the message format according to the error message

3. **Token Issues**
   - Look for status code 401 or 403 with messages about authentication
   - Solution: Update the WhatsApp access token

4. **Recipient Issues**
   - Look for error messages about the recipient not being valid
   - Solution: Verify the phone number format and that the user has opted in

## Next Steps

After testing, please share the complete logs, especially:
1. The command processing logs
2. The message sender logs with the complete API response
3. Any retry attempts and their results

This will help us identify exactly where the issue is occurring and make further improvements.

## WhatsApp Business API Documentation

For reference, here are some useful links to the WhatsApp Business API documentation:

- [WhatsApp Business API Overview](https://developers.facebook.com/docs/whatsapp/api/messages)
- [Sending Messages](https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages)
- [Rate Limits](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/rate-limits)
- [Error Codes](https://developers.facebook.com/docs/whatsapp/cloud-api/support/error-codes) 