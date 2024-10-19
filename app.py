from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import csv
import os
import datetime
from dotenv import load_dotenv
# load the environment variable
load_dotenv()

app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
app.config['DATABASE_URI'] = os.getenv('DATABASE_URI')
app.config['JWT_TOKEN_LOCATION'] = ['headers']


# Initialize JWT
jwt = JWTManager(app)
# Store revoked tokens
revoked_tokens = set()

# Connect to PostgreSQL database
def get_db_connection():
    db_connect = psycopg2.connect(app.config['DATABASE_URI'])
    return db_connect

# 1. Signup: Create a new user account
@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Username and password are required'}), 400
    
    db_connect = get_db_connection()
    cursor = db_connect.cursor()

    try:
        # Check if username already exists
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        if user:
            return jsonify({'message': 'User already exists'}), 400

        # Insert new user into the database
        hashed_password = generate_password_hash(password)
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
        db_connect.commit()

        return jsonify({'message': 'User created successfully'}), 201
    
    except Exception as e:
        db_connect.rollback()
        return jsonify({"message": f"Error: {(e)}"}), 500
    
    finally:
        cursor.close()
        db_connect.close()


# Endpoint 2: Login
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"message": "Missing username or password"}), 400

    db_connect = get_db_connection()
    cursor = db_connect.cursor()

    try:
        # Check if the user exists
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
       
        if not user or not check_password_hash(user[2], password):
            return jsonify({'message': 'Invalid username or password'}), 401

        # Create JWT token
        access_token = create_access_token(identity=user[1],expires_delta=datetime.timedelta(days=2))
        return jsonify(access_token=access_token), 200
    
    except Exception as e:
        db_connect.rollback()
        return jsonify({"message": f"Error: {e}"}), 500
        
    finally:
        cursor.close()
        db_connect.close()


# Endpoint 3: Logout
@app.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    try:
        jti = get_jwt_identity()
        revoked_tokens.add(jti)  # Add token to blacklist (revoked tokens)
        return jsonify({'message': 'logged out successfully'}), 200

    except Exception as e:
            return jsonify({'message': f'Error processing file: {e}'}), 500



# Endpoint 4: fetch_purchase_data_from_csv
@app.route('/fetch_purchase_data_from_csv', methods=['POST'])
@jwt_required()
def fetch_purchase_data_from_csv():

    if 'file' not in request.files:
        return jsonify({'message': 'No file found in the request'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No selected csv file'}), 400
    
    db_connect = get_db_connection()
    cursor = db_connect.cursor()

    upload_folder= './upload_csv'
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
        
    if file.filename.endswith('.csv'):
        try:
            # Secure the filename and save the file
            filename = secure_filename(file.filename)
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)

            # Read and process the CSV file
            with open(file_path, mode='r') as csv_file:
                csv_reader = csv.DictReader(csv_file)

                purchases = {}
                purchase_details = []

                # Process rows in the CSV
                for row in csv_reader:
                    bill_no = row['bill_no']
                    medicine_name = row['medicine_name']
                    quantity = int(row['quantity'])
                    mrp = float(row['mrp'])
                    expiry_date = row['expiry_date']

                    item_total = mrp * quantity

                    # Calculate bill total
                    if bill_no not in purchases:
                        purchases[bill_no] = {
                            'bill_no': bill_no,
                            'bill_date': row['bill_date'],
                            'bill_total': 0,  
                        }

                    purchases[bill_no]['bill_total'] += item_total

                    # Append purchase details
                    purchase_details.append({
                        'bill_no': bill_no,
                        'medicine_name': medicine_name,
                        'quantity': quantity,
                        'mrp': mrp,
                        'item_total': item_total,
                        'expiry_date': expiry_date
                    })

            # Insert data into the purchase and purchase_details tables
            for bill_no, purchase_data in purchases.items():
                # Insert into purchase table
                
                cursor.execute("INSERT INTO purchase (bill_no, bill_date, bill_total) VALUES (%s, %s, %s) RETURNING id",
                                        (purchase_data['bill_no'], purchase_data['bill_date'], purchase_data['bill_total']
                                        ))
                
                purchase_id = cursor.fetchone()[0]

                # Insert into purchase_details table
                for detail in purchase_details:
                    if detail['bill_no'] == bill_no:
                        cursor.execute("""
                            INSERT INTO purchase_details (purchase_id, medicine_name, quantity, mrp, expiry_date)
                            VALUES (%s, %s, %s, %s,  %s)""", 
                            (purchase_id, detail['medicine_name'], detail['quantity'], detail['mrp'], detail['expiry_date']))
                        
                db_connect.commit()
            return jsonify({'message': 'Data processed and inserted successfully'}), 200

        except Exception as e:
            db_connect.rollback()
            return jsonify({'message': f'Error processing file: {e}'}), 500

        finally:
            cursor.close()
            db_connect.close()
    else:
        return jsonify({'message': 'Invalid file type, only CSV files are allowed'}), 400


# Endpoint 5: get_purchase_data
@app.route('/get_purchase_data/<bill_no>', methods=['GET'])
@jwt_required()
def get_purchase_data(bill_no):
    db_connect = get_db_connection()
    cursor = db_connect.cursor()

    try:
        cursor.execute('''SELECT p.id, p.bill_date, p.bill_no, p.bill_total,
                            pd.medicine_name, pd.quantity, pd.mrp, pd.item_total, pd.expiry_date
                            FROM purchase AS p
                            INNER JOIN purchase_details AS pd ON p.id = pd.purchase_id
                            WHERE p.bill_no = %s''', (bill_no,))
        result = cursor.fetchall()
    
        # If no result is found
        if not result:
            return jsonify({'message': f'No purchase found for bill number {bill_no}'}), 404
    
        purchase_data = {
            'bill_no': result[0][2], 
            'bill_date': result[0][1].strftime('%Y-%m-%d'),
            'bill_total': result[0][3],
            'purchase_details': []
        }

        for row in result:
            purchase_data['purchase_details'].append({
                'medicine_name': row[4],
                'quantity': row[5],
                'mrp': row[6],
                'item_total': row[7],
                'expiry_date': row[8].strftime('%Y-%m-%d')
            })

        return jsonify(purchase_data), 200

    except Exception as e:
        return jsonify({'message': f'Error : {e}'}), 500

    finally:
        cursor.close()
        db_connect.close()



# Endpoint 6: update_purchase_detail_data
@app.route('/update_purchase_detail_data/<int:id>', methods=['PUT'])
@jwt_required()
def update_purchase_detail_data(id):
    data = request.get_json()

    new_mrp = data.get('mrp')
    if not new_mrp:
        return jsonify({'message': 'MRP is required'}), 400
    
    db_connect = get_db_connection()
    cursor = db_connect.cursor()

    try:
        cursor.execute("UPDATE purchase_details SET mrp = %s WHERE id = %s", (new_mrp, id))
        if cursor.rowcount == 0:
            return jsonify({'message': f'Record with id {id} not found'}), 404
        
        db_connect.commit()
        return jsonify({'message': 'Record updated successfully'}), 200
    
    except Exception as e:
        db_connect.rollback()
        return jsonify({"message": f"Error: {e}"}), 500
    
    finally:
        cursor.close()
        db_connect.close()


# Endpoint 7: delete_purchase_detail_data
@app.route('/delete_purchase_detail_data/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_purchase_detail_data(id):
    db_connect = get_db_connection()
    cursor = db_connect.cursor()
    
    try:
        cursor.execute("DELETE FROM purchase_details WHERE id = %s", ((id,)))
    
        if cursor.rowcount == 0:
            return jsonify({'message': f'Record with id {id} not found'}), 404
        
        db_connect.commit()

        return jsonify({'message': 'Record deleted successfully'}), 200
    
    except Exception as e:
        db_connect.rollback()
        return jsonify({"message": f"Error: {(e)}"}), 500
    
    finally:
        cursor.close()
        db_connect.close()


# Endpoint 8: create_purchase_csv
@app.route('/create_purchase_csv', methods=['GET'])
@jwt_required()
def create_purchase_csv():
    db_connect = get_db_connection()
    cursor = db_connect.cursor()

    try:
        cursor.execute("""SELECT p.bill_no, p.bill_date, p.bill_total,
               pd.medicine_name, pd.quantity, pd.mrp, pd.item_total, pd.expiry_date
               FROM purchase AS p INNER JOIN purchase_details AS pd ON p.id = pd.purchase_id
        """)

        result = cursor.fetchall()

        if not result:
            return jsonify({'message': 'No purchase data found'}), 404
        
        # Define the CSV file path and name
        csv_file_path = f"purchase_data.csv"

        # Create and write data to the CSV file
        with open(csv_file_path, mode='w',newline="") as csv_file:
            writer = csv.writer(csv_file)

            # Write the header
            writer.writerow(['Bill No', 'Bill Date', 'Bill Total', 'Medicine Name', 'Quantity', 'MRP', 
                             'Item Total', 'Expiry Date'])
            
            # Write the data in rows
            for row in result:
                writer.writerow([
                    row[0], 
                    row[1].strftime('%Y-%m-%d'),  
                    row[2],  
                    row[3],  
                    row[4],  
                    row[5],  
                    row[6],  
                    row[7].strftime('%Y-%m-%d')  
                ])

            return jsonify({'message': 'CSV file created successfully', 'file': csv_file_path}), 200

    except Exception as e:
        return jsonify({'message': f'Error occurred: {e}'}), 500
    
    finally:
        cursor.close()
        db_connect.close()


if __name__ == "__main__":
    app.run(debug=True)