import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",       # or your MySQL username
        password="",       # your MySQL password
        database="expense_tracker"
    )
