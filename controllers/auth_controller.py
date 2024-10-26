from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from functools import wraps
from models.db import Database
from config import Config

# Create a Blueprint for authentication
auth_bp = Blueprint('auth', __name__)

# JWT secret key
JWT_SECRET = Config.JWT_SECRET_KEY

token_blacklist = set()

# Decorator for JWT authentication
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]

        if not token:
            return jsonify({'message': 'Token is missing!'}), 403

        try:
            data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            db = Database()
            current_user = db.find_user_by_username(data['username'])
            db.close()
        except Exception as e:
            return jsonify({'message': 'Token is invalid!'}), 403

        return f(current_user, *args, **kwargs)

    return decorated


# Signup endpoint:- Create a new user account
@auth_bp.route('/signup', methods=['POST'])
def signup():
    # Initialize the base response structure
    response = {"status": "error", "message": ""}

    try :
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

    except Exception as e:
        response["message"] = 'Username and password are required'
        return jsonify(response), 400
    
    if not username or not password:
        response["message"] = "Username and password cannot be null or empty."
        return jsonify(response), 400
    
    db_cursor = Database()
    
    try:
        # Check if username already exists
        user = db_cursor.fetch_one("SELECT * FROM users WHERE username = %s", (username,))
        
        if user:
            response["message"] = 'User already exists'
            return jsonify(response), 400

        # Insert new user into the database
        hashed_password = generate_password_hash(password)
        db_cursor.execute_query("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
        db_cursor.close()

        response["status"] = "success"
        response["message"] = 'User created successfully'
        return jsonify(response), 201
    
    except Exception as e:
        response["message"] = f"An error occurred: {e}"
        return jsonify(response), 500



# Login Endpoint 
@auth_bp.route('/login', methods=['POST'])
def login():
    # Initialize the base response structure
    response = {"status": "error", "message": ""}

    try :
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

    except Exception as e:
        response["message"] = 'Username and password are required'
        return jsonify(response), 400
    
    if not username or not password:
        response["message"] = "Username and password cannot be null or empty."
        return jsonify(response), 400
        
    db_cursor = Database()

    try:
        # Check if the user exists
        user = db_cursor.fetch_one("SELECT * FROM users WHERE username = %s", (username,))
       
        if not user or not check_password_hash(user[2], password):
            response["message"] = "Invalid username or password"
            return jsonify(response), 401

        # Create JWT token
        token = jwt.encode({
            'username': username,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)  # Token expires in 1 days
            }, JWT_SECRET, algorithm="HS256")
        
        db_cursor.close()

        response["status"] = "success"
        response["message"] = 'Login successful.'
        response['data'] = {"token": token, "username": username}

        return jsonify(response), 200
    
    except Exception as e:
        response["message"] = f"An error occurred: {e}"
        return jsonify(response), 500
    


# Logout Endpoint
@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout(current_user):
    try :
        # Invalidate the token by adding it to the blacklist
        token = request.headers['Authorization'].split(" ")[1]
        token_blacklist.add(token)
        return jsonify({ "status": "success","message": "Logged out successfully!"}), 200
    
    except Exception as e:
        return jsonify({ "status": "error", "message": f"An error occurred: {e}"}), 500
