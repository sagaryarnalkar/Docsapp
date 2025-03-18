"""Authentication Routes Module"""


import logging
import traceback
from flask import Blueprint, request, jsonify, current_app
from routes.handlers import AuthHandler

# Create a blueprint for auth routes
auth_bp = Blueprint('auth', __name__)
