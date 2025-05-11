from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
import os

app = Flask(__name__)
app.secret_key = 'your_super_secret_key'  # Change this in production!

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Neon PostgreSQL config
DB_HOST = "ep-icy-surf-abajt2qk-pooler.eu-west-2.aws.neon.tech"
DB_NAME = "neondb"
DB_USER = "neondb_owner"
DB_PASS = "npg_iuK42OmEkMrT"
DB_SSLMODE = "require"

# --- Database connection ---
def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        sslmode=DB_SSLMODE
    )

# --- Routes ---
@app.route('/')
def home():
    return render_template('home.html')


@app.route('/add-client', methods=['GET', 'POST'])
def add_client():
    if request.method == 'POST':
        data = request.form
        files = request.files

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(""" 
            INSERT INTO clients (
                first_name, middle_name, last_name, date_of_birth, gender,
                nationality, phone, email, linkedin, other_social,
                current_address, permanent_address, city, state, country,
                career_objective, education_level, field_of_study, institution_name,
                edu_start_date, edu_end_date, gpa,
                job_title, company_name, industry, work_start_date, work_end_date,
                responsibilities, achievements,
                skill_name, skill_level, skill_years,
                cert_name, cert_org, cert_issue_date, cert_expiry_date,
                language, language_level,
                project_title, project_desc, project_role, project_tech, project_date, project_url,
                ref_name, ref_position, ref_company, ref_contact, ref_relation,
                availability, preferred_roles, preferred_locations, employment_type, salary_range,
                hobbies, relocate,
                id_doc, profile_pic
            ) VALUES (
                %(first_name)s, %(middle_name)s, %(last_name)s, %(date_of_birth)s, %(gender)s,
                %(nationality)s, %(phone)s, %(email)s, %(linkedin)s, %(other_social)s,
                %(current_address)s, %(permanent_address)s, %(city)s, %(state)s, %(country)s,
                %(career_objective)s, %(education_level)s, %(field_of_study)s, %(institution_name)s,
                %(edu_start_date)s, %(edu_end_date)s, %(gpa)s,
                %(job_title)s, %(company_name)s, %(industry)s, %(work_start_date)s, %(work_end_date)s,
                %(responsibilities)s, %(achievements)s,
                %(skill_name)s, %(skill_level)s, %(skill_years)s,
                %(cert_name)s, %(cert_org)s, %(cert_issue_date)s, %(cert_expiry_date)s,
                %(language)s, %(language_level)s,
                %(project_title)s, %(project_desc)s, %(project_role)s, %(project_tech)s, %(project_date)s, %(project_url)s,
                %(ref_name)s, %(ref_position)s, %(ref_company)s, %(ref_contact)s, %(ref_relation)s,
                %(availability)s, %(preferred_roles)s, %(preferred_locations)s, %(employment_type)s, %(salary_range)s,
                %(hobbies)s, %(relocate)s,
                %(id_doc)s, %(profile_pic)s
            )
        """, {
            **data,
            "id_doc": save_file(files.get("id_doc")),
            "profile_pic": save_file(files.get("profile_pic"))
        })

        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('home'))
    
    return render_template('add_client.html')


@app.route('/clients')
def view_clients():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, first_name, middle_name, last_name, phone, email, career_objective FROM clients")
    clients = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("view_clients.html", clients=clients)


@app.route('/delete-client/<int:id>', methods=['POST'])
def delete_client(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM clients WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('view_clients'))


# --- Admin Login ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Replace with actual check (e.g., database or env vars)
        if username == 'admin' and password == 'admin123':
            session['admin_logged_in'] = True
            return redirect(url_for('view_clients'))
        else:
            flash("Invalid credentials. Try again.", "danger")

    return render_template("login.html")


@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('home'))


# --- Helpers ---
def save_file(file):
    if file and file.filename:
        path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(path)
        return file.filename
    return None


if __name__ == '__main__':
    app.run(debug=True)

