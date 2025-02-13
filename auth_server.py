from flask import Flask, request
import os
from dotenv import load_dotenv
from models.user_state import UserState

load_dotenv()

app = Flask(__name__)
user_state = UserState()

@app.route('/')
def home():
    return "Auth server is running!"

@app.route('/oauth2callback')
def oauth2callback():
    # Get authorization code from query parameters
    code = request.args.get('code')
    state = request.args.get('state')
    
    if code:
        # Store the authorization code
        user_state.store_auth_code(code, state)
        return "Authorization successful! You can close this window and return to the test."
    return "Authorization failed!"

if __name__ == '__main__':
    print("\n=== Auth Server Starting ===")
    print("Please keep this server running and use another terminal for testing")
    app.run(port=8080, debug=True) 