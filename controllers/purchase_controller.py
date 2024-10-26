from flask import Blueprint, request, jsonify
from models.db import Database
from .auth_controller import token_required
from werkzeug.utils import secure_filename
import csv
import os

# Create a Blueprint for purchase-related routes
purchase_bp = Blueprint('purchase', __name__)


# Endpoint : fetch_purchase_data_from_csv
@purchase_bp.route('/fetch_purchase_data_from_csv', methods=['POST'])
@token_required
def fetch_purchase_data_from_csv(current_user):
    # Initialize the base response structure
    response = {"status": "error", "message": ""}

    if 'file' not in request.files:
        response['message'] = 'No file found in the request'
        return jsonify(response), 400
    
    file = request.files['file']
    if file.filename == '':
        response['message'] = 'No selected csv file'
        return jsonify(response), 400
    
    db_cursor = Database()

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
                
                purchase_id = db_cursor.fetch_one("INSERT INTO purchase (bill_no, bill_date, bill_total) VALUES (%s, %s, %s) RETURNING id",
                                        (purchase_data['bill_no'], purchase_data['bill_date'], purchase_data['bill_total']
                                        ))[0]
                
                # Insert into purchase_details table
                for detail in purchase_details:
                    if detail['bill_no'] == bill_no:
                        db_cursor.execute_query("""
                            INSERT INTO purchase_details (purchase_id, medicine_name, quantity, mrp, expiry_date)
                            VALUES (%s, %s, %s, %s,  %s)""", 
                            (purchase_id, detail['medicine_name'], detail['quantity'], detail['mrp'], 
                             detail['expiry_date']))

            db_cursor.close()

            response["status"] = "success"
            response["message"] = 'Data processed and inserted successfully'         
            return jsonify(response), 200

        except Exception as e:
            response['message'] = f'Error processing file: {e}'
            return jsonify(response), 500

    else:
        response['message'] = 'Invalid file type, only CSV files are allowed'
        return jsonify(response), 400



# Endpoint : get_purchase_data
@purchase_bp.route('/get_purchase_data/<bill_no>', methods=['GET'])
@token_required
def get_purchase_data(current_user,bill_no):
    # Initialize the base response structure
    response = {"status": "error", "message": ""}

    db_cursor = Database()
    
    try:
        result = db_cursor.fetch_all('''SELECT p.id, p.bill_date, p.bill_no, p.bill_total,
                            pd.medicine_name, pd.quantity, pd.mrp, pd.item_total, pd.expiry_date
                            FROM purchase AS p
                            INNER JOIN purchase_details AS pd ON p.id = pd.purchase_id
                            WHERE p.bill_no = %s''', (bill_no,))
    
        # If no result is found
        if not result:
            response['message'] = f'No purchase found for bill number {bill_no}'
            return jsonify(response), 404
    
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

        db_cursor.close()

        response["status"] = "success"
        response['message'] = "Purchase data retrieved successfully."
        response['data'] = purchase_data
        return jsonify(response), 200

    except Exception as e:
        response["message"] = f"An error occurred: {e}"
        return jsonify(response), 500


# Endpoint : update_purchase_detail_data
@purchase_bp.route('/update_purchase_detail_data/<int:id>', methods=['PUT'])
@token_required
def update_purchase_detail_data(current_user, id): 
    # Initialize the base response structure
    response = {"status": "error", "message": ""}

    try:
        data = request.get_json()
        new_mrp = data.get('mrp')
    except:
        response['message'] = "MRP is required"
        return jsonify(response), 400
    
    if not new_mrp:
        response['message'] = 'MRP value must be greater than zero.'
        return jsonify(response), 400
    
    db_cursor = Database()

    try:
        if not db_cursor.fetch_one("SELECT * from purchase_details WHERE id= %s",(id,)):
            response['message'] = f'Record with id {id} not found'
            return jsonify(response), 404
        
        db_cursor.execute_query("UPDATE purchase_details SET mrp = %s WHERE id = %s", (new_mrp, id))
        db_cursor.close()

        response["status"] = "success"
        response['message'] = 'Record updated successfully'
        return jsonify(response), 200
    
    except Exception as e:
        response["message"] = f"An error occurred: {e}"
        return jsonify(response), 500
        
    

# Endpoint : delete_purchase_detail_data
@purchase_bp.route('/delete_purchase_detail_data/<int:id>', methods=['DELETE'])
@token_required
def delete_purchase_detail_data(current_user,id):
    # Initialize the base response structure
    response = {"status": "error", "message": ""}

    db_cursor = Database()
    
    try:
        if not db_cursor.fetch_one("SELECT * from purchase_details WHERE id= %s",(id,)):
            response['message'] = f'Record with id {id} not found'
            return jsonify(response), 404
        
        db_cursor.execute_query("DELETE FROM purchase_details WHERE id = %s", ((id,)))
        db_cursor.close()

        response['status'] = "success"
        response['message'] = 'Record deleted successfully'
        return jsonify(response), 200

    except Exception as e:
        response["message"] = f"An error occurred: {e}"
        return jsonify(response), 500



# Endpoint : create_purchase_csv
@purchase_bp.route('/create_purchase_csv', methods=['GET'])
@token_required
def create_purchase_csv(current_user):
    # Initialize the base response structure
    response = {"status": "error", "message": ""}

    db_cursor = Database()

    try:
        result = db_cursor.fetch_all("""SELECT p.bill_no, p.bill_date, p.bill_total,
               pd.medicine_name, pd.quantity, pd.mrp, pd.item_total, pd.expiry_date
               FROM purchase AS p INNER JOIN purchase_details AS pd ON p.id = pd.purchase_id
                """)

        if not result:
            response['message'] = 'No purchase data found'
            return jsonify(response), 404
        
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

        db_cursor.close()

        response['status'] = "success"
        response['message'] = 'CSV file created successfully'
        response['file'] = csv_file_path
        return jsonify(response), 200

    except Exception as e:
        response["message"] = f"An error occurred: {e}"
        return jsonify(response), 500
