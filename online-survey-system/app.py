from flask import Flask, render_template, request, redirect, session
from flask_mysqldb import MySQL
from functools import wraps
from flask import send_file
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
from openpyxl import Workbook
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Non-GUI backend, required for servers
import matplotlib.pyplot as plt
import hashlib
import config

app = Flask(__name__)

app.secret_key = config.SECRET_KEY  # Move this to config.py, use a long random string

app.config['MYSQL_HOST'] = config.MYSQL_HOST
app.config['MYSQL_USER'] = config.MYSQL_USER
app.config['MYSQL_PASSWORD'] = config.MYSQL_PASSWORD
app.config['MYSQL_DB'] = config.MYSQL_DB
app.config["MYSQL_PORT"] = config.MYSQL_PORT

mysql = MySQL(app)


# --- Helper ---

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# --- Auth decorator ---

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated


# --- Routes ---

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = hash_password(request.form['password'])

        cur = mysql.connection.cursor()

        # Check if email already exists
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            error = "Email already registered."
        else:
            cur.execute(
                "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                (username, email, password)
            )
            mysql.connection.commit()
            return redirect('/login')

    return render_template('register.html', error=error)


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form['email']
        password = hash_password(request.form['password'])

        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT id, username FROM users WHERE email = %s AND password = %s",
            (email, password)
        )
        user = cur.fetchone()

        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect('/dashboard')
        else:
            error = "Invalid email or password."

    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', username=session['username'])


@app.route('/create-survey', methods=['GET', 'POST'])
@login_required
def create_survey():

    if request.method == 'POST':

        title = request.form['title']
        description = request.form['description']
        user_id = session['user_id']

        cur = mysql.connection.cursor()

        # Save survey
        cur.execute(
            """
            INSERT INTO surveys
            (title, description, created_by)
            VALUES (%s, %s, %s)
            """,
            (title, description, user_id)
        )

        mysql.connection.commit()

        survey_id = cur.lastrowid

        # Get all questions and types
        questions = request.form.getlist('questions[]')
        types = request.form.getlist('types[]')

        # Save every question
        for index, (question, qtype) in enumerate(zip(questions, types), start=1):

            if question.strip():

                cur.execute(
                    """
                    INSERT INTO questions
                    (survey_id, question, question_type)
                    VALUES (%s, %s, %s)
                    """,
                    (
                        survey_id,
                        question,
                        qtype
                    )
                )

                mysql.connection.commit()

                # Get inserted question id
                question_id = cur.lastrowid

                # Save MCQ options
                if qtype == "mcq":

                    options = request.form.getlist(f"options_{index}[]")

                    for option in options:

                        if option.strip():

                            cur.execute(
                                """
                                INSERT INTO question_options
                                (question_id, option_text)
                                VALUES (%s, %s)
                                """,
                                (
                                    question_id,
                                    option
                                )
                            )

        mysql.connection.commit()

        return redirect('/surveys')

    return render_template('create_survey.html')


@app.route('/surveys')
@login_required
def surveys():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM surveys")
    surveys = cur.fetchall()
    return render_template('surveys.html', surveys=surveys)


@app.route('/survey/<int:survey_id>', methods=['GET', 'POST'])
@login_required
def survey(survey_id):

    cur = mysql.connection.cursor()

    # Get survey details
    cur.execute(
        "SELECT * FROM surveys WHERE id=%s",
        (survey_id,)
    )

    survey = cur.fetchone()

    if not survey:
        return "Survey not found", 404

    # Get questions
    cur.execute(
        """
        SELECT id, question, question_type
        FROM questions
        WHERE survey_id=%s
        """,
        (survey_id,)
    )

    question_rows = cur.fetchall()

    questions = []

    for row in question_rows:

        question = {
            "id": row[0],
            "question": row[1],
            "type": row[2],
            "options": []
        }

        # Load MCQ options
        if row[2] == "mcq":

            cur.execute(
                """
                SELECT option_text
                FROM question_options
                WHERE question_id=%s
                """,
                (row[0],)
            )

            question["options"] = cur.fetchall()

        questions.append(question)

    # Save responses
    if request.method == "POST":

        for question in questions:

            question_id = question["id"]

            answer = request.form.get(
                f"question_{question_id}"
            )

            if answer:

                cur.execute(
                    """
                    INSERT INTO responses
                    (survey_id, question_id, user_id, answer)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        survey_id,
                        question_id,
                        session["user_id"],
                        answer
                    )
                )

        mysql.connection.commit()

        return redirect(f"/analytics/{survey_id}")

    return render_template(
        "survey.html",
        survey=survey,
        questions=questions
    )


@app.route('/analytics/<int:survey_id>')
@login_required
def analytics(survey_id):

    cur = mysql.connection.cursor()

    cur.execute(
        "SELECT answer FROM responses WHERE survey_id = %s",
        (survey_id,)
    )

    data = cur.fetchall()

    chart_available = False

    if data:

        answers = [row[0] for row in data]

        df = pd.DataFrame(answers, columns=['answers'])

        counts = df['answers'].value_counts()

        plt.figure(figsize=(7,5))

        counts.plot(kind='bar')

        plt.title("Survey Analysis")
        plt.xlabel("Response")
        plt.ylabel("Number of Responses")

        plt.tight_layout()

        plt.savefig("static/images/chart.png")

        plt.close()

        chart_available = True

    return render_template(
        "analytics.html",
        chart_available=chart_available,
        survey_id=survey_id
    )


@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html')


@app.route('/download-pdf')
@login_required
def download_pdf():

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT s.title,
               u.username,
               r.answer
        FROM responses r
        JOIN surveys s ON r.survey_id = s.id
        JOIN users u ON r.user_id = u.id
    """)

    rows = cur.fetchall()

    pdf_file = "survey_report.pdf"

    doc = SimpleDocTemplate(pdf_file)

    data = [["Survey", "User", "Answer"]]

    for row in rows:
        data.append(list(row))

    table = Table(data)

    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.blue),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 1, colors.black),
        ("BACKGROUND", (0,1), (-1,-1), colors.beige),
        ("BOTTOMPADDING", (0,0), (-1,0), 10)
    ]))

    doc.build([table])

    return send_file(
        pdf_file,
        as_attachment=True
    )


@app.route('/download-excel')
@login_required
def download_excel():

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT s.title,
               u.username,
               r.answer
        FROM responses r
        JOIN surveys s ON r.survey_id = s.id
        JOIN users u ON r.user_id = u.id
    """)

    rows = cur.fetchall()

    wb = Workbook()

    ws = wb.active

    ws.title = "Survey Report"

    ws.append(["Survey", "User", "Answer"])

    for row in rows:
        ws.append(row)

    excel_file = "survey_report.xlsx"

    wb.save(excel_file)

    return send_file(
        excel_file,
        as_attachment=True
    )


if __name__ == "__main__":
    app.run(debug=True)
