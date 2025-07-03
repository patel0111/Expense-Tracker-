from flask import Flask, render_template, request, redirect, session, url_for, Response
from dbconfig import get_connection
from werkzeug.security import generate_password_hash, check_password_hash
import csv, io
from decimal import Decimal

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# ======================= ROUTES =======================

@app.route('/')
def home():
    return redirect('/login')

# ------------------- Register -------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                       (username, email, password))
        user_id = cursor.lastrowid

        # Default categories
        default_cats = ['Food', 'Rent', 'Transport', 'Utilities', 'Entertainment']
        for c in default_cats:
            cursor.execute("INSERT INTO categories (user_id, name) VALUES (%s, %s)", (user_id, c))

        conn.commit()
        cursor.close()
        conn.close()
        return redirect('/login')

    return render_template('register.html')

# ------------------- Login -------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password_input = request.form['password']

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user[2], password_input):
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect('/dashboard')
        else:
            return "Invalid credentials"
    return render_template('login.html')

# ------------------- Logout -------------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ------------------- Dashboard -------------------
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = get_connection()
    cursor = conn.cursor()

    # Get total expenses
    cursor.execute("SELECT IFNULL(SUM(amount), 0) FROM expenses WHERE user_id = %s", (user_id,))
    total_expenses = cursor.fetchone()[0]

    # Get user's monthly budget
    cursor.execute("SELECT budget_monthly FROM users WHERE id = %s", (user_id,))
    result = cursor.fetchone()
    budget = result[0] if result else None

    # Convert budget and total_expenses to Decimal
    if budget is not None:
        budget = Decimal(budget)
        ninety_percent_budget = budget * Decimal('0.9')
    else:
        ninety_percent_budget = None

    cursor.close()
    conn.close()

    return render_template('dashboard.html',
                           username=session['username'],
                           total_expenses=total_expenses,
                           budget=budget,
                           ninety_percent_budget=ninety_percent_budget)

# ------------------- Add Expense -------------------
@app.route('/add-expense', methods=['GET', 'POST'])
def add_expense():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        amount = request.form['amount']
        category_id = request.form['category_id']
        expense_date = request.form['expense_date']
        description = request.form['description']
        cursor.execute("""
            INSERT INTO expenses (user_id, category_id, amount, description, expense_date)
            VALUES (%s, %s, %s, %s, %s)
        """, (session['user_id'], category_id, amount, description, expense_date))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect('/view-expenses')

    cursor.execute("SELECT id, name FROM categories WHERE user_id = %s", (session['user_id'],))
    categories = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('add_expense.html', categories=categories)

# ------------------- View Expenses -------------------
@app.route('/view-expenses')
def view_expenses():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.id, e.amount, c.name, e.description, e.expense_date 
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = %s
        ORDER BY e.expense_date DESC
    """, (session['user_id'],))
    expenses = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('view_expenses.html', expenses=expenses)

# ------------------- Edit Expense -------------------
@app.route('/edit-expense/<int:id>', methods=['GET', 'POST'])
def edit_expense(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        amount = request.form['amount']
        category_id = request.form['category_id']
        expense_date = request.form['expense_date']
        description = request.form['description']
        cursor.execute("""
            UPDATE expenses
            SET amount=%s, category_id=%s, description=%s, expense_date=%s
            WHERE id=%s AND user_id=%s
        """, (amount, category_id, description, expense_date, id, session['user_id']))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect('/view-expenses')

    cursor.execute("SELECT amount, category_id, expense_date, description FROM expenses WHERE id=%s AND user_id=%s",
                   (id, session['user_id']))
    expense = cursor.fetchone()

    cursor.execute("SELECT id, name FROM categories WHERE user_id = %s", (session['user_id'],))
    categories = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('add_expense.html', expense=expense, categories=categories, edit=True)

# ------------------- Delete Expense -------------------
@app.route('/delete-expense/<int:id>')
def delete_expense(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE id = %s AND user_id = %s", (id, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect('/view-expenses')

# ------------------- Reports -------------------
@app.route('/reports')
def reports():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.name, SUM(e.amount)
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = %s
        GROUP BY c.name
    """, (session['user_id'],))
    results = cursor.fetchall()
    cursor.close()
    conn.close()

    labels = [row[0] for row in results]
    data = [float(row[1]) for row in results]

    return render_template('reports.html', labels=labels, data=data)

# ------------------- Profile (Budget) -------------------
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        budget = request.form['budget']
        cursor.execute("UPDATE users SET budget_monthly=%s WHERE id=%s", (budget, session['user_id']))
        conn.commit()

    cursor.execute("SELECT budget_monthly FROM users WHERE id=%s", (session['user_id'],))
    budget = cursor.fetchone()[0] or 0
    cursor.close()
    conn.close()
    return render_template('profile.html', budget=budget)

# ------------------- Export CSV -------------------
@app.route('/export-csv')
def export_csv():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.id, u.username, c.name, e.amount, e.description, e.expense_date
        FROM expenses e
        JOIN users u ON e.user_id = u.id
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = %s
    """, (session['user_id'],))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'User', 'Category', 'Amount', 'Description', 'Date'])
    cw.writerows(rows)
    output = si.getvalue().encode('utf-8')

    return Response(output, mimetype='text/csv',
                    headers={"Content-Disposition": "attachment;filename=expenses.csv"})

# ======================= END =======================
if __name__ == '__main__':
    app.run(debug=True)
