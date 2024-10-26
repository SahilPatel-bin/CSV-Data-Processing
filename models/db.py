import psycopg2
from config import Config

class Database:
    def __init__(self):
        # Connect to the PostgreSQL database
        try:
            self.connection = psycopg2.connect(Config.DATABASE_URI)
            self.cursor = self.connection.cursor()

        except Exception as e:
            return f"Database connection failed: {e}"
            
    def execute_query(self, query, params=None):
        """Executes a single query."""
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)

            self.connection.commit()
    
        except Exception as e:
            self.connection.rollback()

    def fetch_all(self, query, params=None):
        """Fetches all results from a query."""
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            results = self.cursor.fetchall()
        
            return results
        
        except Exception as e:
            return []

    def fetch_one(self, query, params=None):
        """Fetches a single result from a query."""
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)

            result = self.cursor.fetchone()
            return result
        
        except Exception as e:
            return None

    def close(self):
        """Closes the database connection."""
        self.cursor.close()
        self.connection.close()

    def find_user_by_username(self,username):
        return self.fetch_one("SELECT username from users where username= %s",(username,))
        