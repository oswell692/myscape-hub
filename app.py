from flask import Flask, make_response, Response, render_template, request, redirect, url_for, session, flash
import psycopg2
import os
import bcrypt
from weasyprint import HTML
from datetime import datetime

# Hardcoded admin credentials
ADMIN_USERNAME = "myscape@gmail.com"
ADMIN_HASHED_PASSWORD = "$2b$12$gdZtv.S7O2xeDLqJMYvm.O0WAYH033wcIqhDIZyi8wXMwtA6/Hmly"

app = Flask(__name__)
app.secret_key = '0c9cc5725e5cdadf1066ced0abe62e41'

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def save_uploaded_file(file, column_name, client_id, cursor):
    if file:
        binary_data = file.read()
        cursor.execute(
            f"UPDATE clients SET {column_name} = %s WHERE client_id = %s",
            (psycopg2.Binary(binary_data), client_id)
        )

@app.route('/upload_files/<int:client_id>', methods=['POST'])
def upload_files(client_id):
    profile_pic = request.files.get('profile_pic')
    id_doc = request.files.get('id_doc')

    conn = get_db_connection()
    cursor = conn.cursor()

    save_uploaded_file(profile_pic, 'profile_pic', client_id, cursor)
    save_uploaded_file(id_doc, 'id_doc', client_id, cursor)

    conn.commit()
    cursor.close()
    conn.close()
    return "Files uploaded successfully"

DB_HOST = "ep-icy-surf-abajt2qk-pooler.eu-west-2.aws.neon.tech"
DB_NAME = "neondb"
DB_USER = "neondb_owner"
DB_PASS = "npg_iuK42OmEkMrT"
DB_SSLMODE = "require"

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        sslmode=DB_SSLMODE
    )

@app.route('/view_profile_pic/<int:client_id>')
def view_profile_pic(client_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT profile_pic FROM clients WHERE client_id = %s", (client_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if result and result[0]:
        return Response(result[0], mimetype='image/jpeg')  # or image/png/pdf
    return "No profile picture found", 404

@app.route('/view_id_doc/<int:client_id>')
def view_id_doc(client_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_doc FROM clients WHERE client_id = %s", (client_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if result and result[0]:
        return Response(result[0], mimetype='application/pdf')  # or image/jpeg/png
    return "No ID document found", 404


@app.template_filter('format_date')
def format_date(value, format='%b %Y'):
    if not value:
        return ''
    if isinstance(value, str):
        try:
            value = datetime.strptime(value, '%Y-%m-%d')  # your date format
        except ValueError:
            return value
    return value.strftime(format)
from psycopg2 import sql

def get_client_full_details(email=None, client_id=None):
    if not email and not client_id:
        return None

    # Determine the filter field and its value
    field = 'email' if email else 'id'
    value = email if email else client_id

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Fetch all matching clients
            query = sql.SQL("SELECT * FROM clients WHERE {} = %s").format(sql.Identifier(field))
            cur.execute(query, (value,))
            clients = cur.fetchall()

            if not clients:
                return None

            all_data = []

            for client in clients:
                current_client_id = client[0]  # Assuming client_id is first column

                # Helper to fetch related data for each client
                def fetch_all_from_table(table_name):
                    sub_query = sql.SQL("SELECT * FROM {} WHERE client_id = %s").format(sql.Identifier(table_name))
                    cur.execute(sub_query, (current_client_id,))
                    return cur.fetchall()
                data = {
                        'client': client,
                        'skills': fetch_all_from_table('client_skills'),
                        'certifications': fetch_all_from_table('client_certifications'),
                        'languages': fetch_all_from_table('client_languages'),
                        'projects': fetch_all_from_table('client_projects'),
                        'references': fetch_all_from_table('client_references'),
                        'work_experience': fetch_all_from_table('client_work_experience')
                    }
                return data  # ✅ a dictionary!


                


@app.route('/download_resume/<int:client_id>')
def download_resume(client_id):
    details = get_client_full_details(client_id=client_id)
    if not details:
        return "Client not found", 404

    rendered = render_template('resume_template.html', **details)
    pdf = HTML(string=rendered).write_pdf()

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=client_{client_id}_resume.pdf'
    return response


@app.route('/')
def home():
    return render_template('home.html')

@app.route('/submission-status')
def submission_status():
    status = request.args.get('status')
    error_message = request.args.get('msg')
    return render_template('submission_status.html', status=status, error_message=error_message)

@app.route('/add-client', methods=['GET', 'POST'])
@app.route('/edit-client/<int:client_id>', methods=['GET', 'POST'])
def add_client(client_id=None):
    conn = None
    client_data = None

    if request.method == 'GET' and client_id is not None:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM clients WHERE id = %s", (client_id,))
            client_row = cur.fetchone()
            if client_row:
                columns = [desc[0] for desc in cur.description]
                client_data = dict(zip(columns, client_row))
            cur.close()
        except Exception as e:
            print(f"❌ ERROR FETCHING CLIENT: {str(e)}")
        finally:
            if conn:
                conn.close()

    if request.method == 'POST':
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            # If editing, fetch old filenames to keep if no new upload
            old_id_doc = None
            old_profile_pic = None
            if client_id:
                cur.execute("SELECT id_doc, profile_pic FROM clients WHERE id = %s", (client_id,))
                old_files = cur.fetchone()
                if old_files:
                    old_id_doc, old_profile_pic = old_files

            # Save new files or keep old ones
            id_doc_file = request.files.get('id_doc')
            profile_pic_file = request.files.get('profile_pic')
            
            id_doc = save_uploaded_file(id_doc_file, 'id_doc', client_id, cur) if id_doc_file and id_doc_file.filename else old_id_doc
            profile_pic = save_uploaded_file(profile_pic_file, 'profile_pic', client_id, cur) if profile_pic_file and profile_pic_file.filename else old_profile_pic

            state = request.form.get('state')
            state_other = request.form.get('state_other')
            country = request.form.get('country')
            country_other = request.form.get('country_other')

# Case-insensitive check to ensure "Other", "other", etc. all work
            final_state = state_other if state and state.strip().lower() == "other" else state
            final_country = country_other if country and country.strip().lower() == "other" else country

            data = {
                'first_name': request.form.get('first_name'),
                'middle_name': request.form.get('middle_name'),
                'last_name': request.form.get('last_name'),
                'date_of_birth': request.form.get('date_of_birth'),
                'gender': request.form.get('gender'),
                'nationality': request.form.get('nationality'),
                'phone': request.form.get('phone'),
                'email': request.form.get('email'),
                'linkedin': request.form.get('linkedin'),
                'other_social': request.form.get('other_social'),
                'current_address': request.form.get('current_address'),
                'permanent_address': request.form.get('permanent_address'),
                'city': request.form.get('city'),
                'state': final_state,
                'country': final_country,
                'career_objective': request.form.get('career_objective'),
                'education_level': request.form.get('education_level'),
                'field_of_study': request.form.get('field_of_study'),
                'institution_name': request.form.get('institution_name'),
                'edu_start_date': request.form.get('edu_start_date'),
                'edu_end_date': request.form.get('edu_end_date'),
                'gpa': request.form.get('gpa'),
                'availability': request.form.get('availability'),
                'preferred_roles': request.form.get('preferred_roles'),
                'preferred_locations': request.form.get('preferred_locations'),
                'employment_type': request.form.get('employment_type'),
                'salary_range': request.form.get('salary_range'),
                'relocate': request.form.get('relocate'),
                'additional_notes': request.form.get('additional_notes'),
                'id_doc': id_doc,
                'profile_pic': profile_pic
            }

            if client_id:  
                # UPDATE existing client
                cur.execute("""
                    UPDATE clients SET
                        first_name=%(first_name)s, middle_name=%(middle_name)s, last_name=%(last_name)s,
                        date_of_birth=%(date_of_birth)s, gender=%(gender)s, nationality=%(nationality)s,
                        phone=%(phone)s, email=%(email)s, linkedin=%(linkedin)s, other_social=%(other_social)s,
                        current_address=%(current_address)s, permanent_address=%(permanent_address)s,
                        city=%(city)s, state=%(state)s, country=%(country)s, career_objective=%(career_objective)s,
                        education_level=%(education_level)s, field_of_study=%(field_of_study)s,
                        institution_name=%(institution_name)s, edu_start_date=%(edu_start_date)s, edu_end_date=%(edu_end_date)s,
                        gpa=%(gpa)s, availability=%(availability)s, preferred_roles=%(preferred_roles)s,
                        preferred_locations=%(preferred_locations)s, employment_type=%(employment_type)s,
                        salary_range=%(salary_range)s, relocate=%(relocate)s, additional_notes=%(additional_notes)s,
                        id_doc=%(id_doc)s, profile_pic=%(profile_pic)s
                    WHERE id = %(client_id)s
                """, {**data, 'client_id': client_id})

                # Delete old related entries to replace them
                cur.execute("DELETE FROM client_work_experience WHERE client_id = %s", (client_id,))
                cur.execute("DELETE FROM client_skills WHERE client_id = %s", (client_id,))
                cur.execute("DELETE FROM client_certifications WHERE client_id = %s", (client_id,))
                cur.execute("DELETE FROM client_languages WHERE client_id = %s", (client_id,))
                cur.execute("DELETE FROM client_projects WHERE client_id = %s", (client_id,))
                cur.execute("DELETE FROM client_references WHERE client_id = %s", (client_id,))

                used_id = client_id
            else:
                # check if email already exists
                cur.execute("SELECT id FROM clients WHERE email = %s", (data['email'],))
                existing_client = cur.fetchone()

                if existing_client:
                    error_message = "A client with this email already exists."
                    return render_template('add_client.html', error=error_message, **data)

                else:
                # INSERT new client
                 cur.execute("""
                    INSERT INTO clients (
                        first_name, middle_name, last_name, date_of_birth, gender, nationality,
                        phone, email, linkedin, other_social, current_address, permanent_address,
                        city, state, country, career_objective, education_level, field_of_study,
                        institution_name, edu_start_date, edu_end_date, gpa, availability, preferred_roles, preferred_locations,
                        employment_type, salary_range, relocate, id_doc, profile_pic, additional_notes
                    ) VALUES (
                        %(first_name)s, %(middle_name)s, %(last_name)s, %(date_of_birth)s, %(gender)s, %(nationality)s,
                        %(phone)s, %(email)s, %(linkedin)s, %(other_social)s, %(current_address)s, %(permanent_address)s,
                        %(city)s, %(state)s, %(country)s, %(career_objective)s, %(education_level)s, %(field_of_study)s,
                        %(institution_name)s, %(edu_start_date)s, %(edu_end_date)s, %(gpa)s, %(availability)s, %(preferred_roles)s, %(preferred_locations)s,
                        %(employment_type)s, %(salary_range)s, %(relocate)s, %(id_doc)s, %(profile_pic)s, %(additional_notes)s
                    ) RETURNING id
                """, data)
                used_id = cur.fetchone()[0]

            # Insert related data (work experience, skills, etc) for both add and edit
            job_titles = request.form.getlist('job_title[]')
            company_names = request.form.getlist('company_name[]')
            industries = request.form.getlist('industry[]')
            start_dates = request.form.getlist('work_start_date[]')
            end_dates = request.form.getlist('work_end_date[]')
            responsibilities = request.form.getlist('responsibilities[]')
            achievements = request.form.getlist('achievements[]')

# Ensure all lists are of the same length
            work_exps = zip(job_titles, company_names, industries, start_dates, end_dates, responsibilities, achievements)

            for title, company, industry, start, end, resp, achieve in work_exps:
                if title.strip():  # You can add more validations if needed
                    cur.execute("""
                        INSERT INTO client_work_experience (
                            client_id, job_title, company_name, industry,
                            work_start_date, work_end_date, responsibilities, achievements
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (used_id, title, company, industry, start, end, resp, achieve))

            skill_names = request.form.getlist('skill_name[]')
            skill_levels = request.form.getlist('skill_level[]')
            skill_years = request.form.getlist('skill_years[]')

            skills = zip(skill_names, skill_levels, skill_years)

            for name, level, years in skills:
                if name.strip():  # Ensure skill name isn't blank
                    cur.execute("""
                        INSERT INTO client_skills (client_id, skill_name, skill_level, skill_years)
                        VALUES (%s, %s, %s, %s)
                     """, (used_id, name, level, years))


            cert_names = request.form.getlist('cert_name[]')
            cert_orgs = request.form.getlist('cert_org[]')
            cert_issues = request.form.getlist('cert_issue_date[]')
            cert_expires = request.form.getlist('cert_expiry_date[]')

            certs = zip(cert_names, cert_orgs, cert_issues, cert_expires)

            for name, org, issue, expiry in certs:
                if name.strip():  # Avoid blank entries
                    cur.execute("""
                        INSERT INTO client_certifications (
                        client_id, cert_name, cert_org, cert_issue_date, cert_expiry_date
                        )
                        VALUES (%s, %s, %s, %s, %s)
                    """, (used_id, name, org, issue or None, expiry or None))

            langs = zip(
                request.form.getlist('language[]'),
                request.form.getlist('language_level[]')
            )
            for lang, level in langs:
                if lang.strip():
                    cur.execute("""
                        INSERT INTO client_languages (client_id, language, language_level)
                        VALUES (%s, %s, %s)
                    """, (used_id, lang, level))

            projects = zip(
                request.form.getlist('project_title[]'),
                request.form.getlist('project_desc[]'),
                request.form.getlist('project_role[]'),
                request.form.getlist('project_tech[]'),
                request.form.getlist('project_date[]'),
                request.form.getlist('project_url[]')
            )
            for title, desc, role, tech, date, url in projects:
                if title.strip():
                    cur.execute("""
                        INSERT INTO client_projects (client_id, project_title, project_desc, project_role, project_tech, project_date, project_url)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (used_id, title, desc, role, tech, date or None, url))

            refs = zip(
                request.form.getlist('ref_name[]'),
                request.form.getlist('ref_position[]'),
                request.form.getlist('ref_company[]'),
                request.form.getlist('ref_contact[]'),
                request.form.getlist('ref_relation[]')
            )
            for name, pos, comp, contact, relation in refs:
                if name.strip():
                    cur.execute("""
                        INSERT INTO client_references (client_id, ref_name, ref_position, ref_company, ref_contact, ref_relation)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (used_id, name, pos, comp, contact, relation))

            conn.commit()

            if client_id:
                flash("Client updated successfully!", "success")
            else:
                flash("Client added successfully!", "success")

            return redirect(url_for('submission_status', status='success'))

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"❌ DATABASE ERROR: {str(e)}")

            error_message = str(e)
            if "duplicate key value violates unique constraint" in error_message:
                error_message = "A client with this email already exists."
            return redirect(url_for('submission_status',  status='error', msg=error_message))
    return render_template('add_client.html', client=client_data, client_id=client_id)
    


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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == ADMIN_USERNAME and bcrypt.checkpw(password.encode('utf-8'), ADMIN_HASHED_PASSWORD.encode('utf-8')):
            session['admin_logged_in'] = True
            flash('Welcome, Admin!', 'success')
            return redirect(url_for('view_clients'))  
        else:
            flash('Invalid username or password', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)

