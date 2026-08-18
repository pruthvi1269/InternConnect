from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pymysql
import psycopg2
from psycopg2.extras import RealDictCursor
import os

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "dev-secret-key"
)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "internconnect")

DATABASE_URL = os.getenv("DATABASE_URL")


PROFILE_FOLDER = os.path.join(
    app.root_path,
    "static",
    "uploads",
    "profiles"
)

RESUME_FOLDER = os.path.join(
    app.root_path,
    "static",
    "uploads",
    "resumes"
)

os.makedirs(PROFILE_FOLDER, exist_ok=True)
os.makedirs(RESUME_FOLDER, exist_ok=True)


ALLOWED_IMAGE_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}

ALLOWED_RESUME_EXTENSIONS = {
    "pdf",
    "doc",
    "docx"
}


UPLOAD_FOLDER = os.path.join(
    "static",
    "uploads"
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)



def get_db():

    if DATABASE_URL:

        return psycopg2.connect(
            DATABASE_URL,
            sslmode="require",
            cursor_factory=RealDictCursor
        )

    return pymysql.connect(
        host=DB_HOST,
        port=int(DB_PORT),
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        charset="utf8mb4"
    )



def login_required():

    return "user_id" in session
def admin_required():

    return (
        "user_id" in session
        and session.get("user_type") == "admin"
    )


def allowed_resume(filename):

    return (
        "." in filename
        and
        filename.rsplit(".", 1)[1].lower()
        in ALLOWED_RESUME_EXTENSIONS
    )



@app.route("/")
def home():

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT internships.*, companies.company_name
        FROM internships
        JOIN companies
            ON internships.company_id = companies.id
        WHERE internships.status = 'Open'
        ORDER BY internships.id DESC
        LIMIT 6
    """)

    internships = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "index.html",
        internships=internships
    )


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]
        user_type = request.form["user_type"]

        if not name or not email or not password:

            flash(
                "Please fill all required fields.",
                "danger"
            )

            return redirect(
                url_for("register")
            )

        if user_type not in ["student", "company"]:

            flash(
                "Invalid account type.",
                "danger"
            )

            return redirect(
                url_for("register")
            )

        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "SELECT id FROM users WHERE email=%s",
            (email,)
        )

        existing = cursor.fetchone()

        if existing:

            cursor.close()
            db.close()

            flash(
                "Email is already registered.",
                "danger"
            )

            return redirect(
                url_for("register")
            )

        password_hash = generate_password_hash(
            password
        )

        cursor.execute(
            """
            INSERT INTO users
            (name, email, password, user_type)
            VALUES (%s, %s, %s, %s)
            """,
            (
                name,
                email,
                password_hash,
                user_type
            )
        )


        cursor.execute(
            "SELECT id FROM users WHERE email=%s",
            (email,)
        )

        user = cursor.fetchone()

        user_id = user["id"]

        if user_type == "student":

            cursor.execute(
                """
                INSERT INTO students
                (user_id, full_name)
                VALUES (%s, %s)
                """,
                (
                    user_id,
                    name
                )
            )

        else:

            cursor.execute(
                """
                INSERT INTO companies
                (user_id, company_name)
                VALUES (%s, %s)
                """,
                (
                    user_id,
                    name
                )
            )

        db.commit()

        cursor.close()
        db.close()

        flash(
            "Registration successful. Please login.",
            "success"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )



@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip()
        password = request.form["password"]

        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE email=%s",
            (email,)
        )

        user = cursor.fetchone()

        cursor.close()
        db.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["email"] = user["email"]
            session["user_type"] = user["user_type"]
            if user["user_type"] == "admin":
                return redirect(
                    url_for("admin_dashboard")
                    )
            
            if user["user_type"] == "student":

                return redirect(
                    url_for("student_dashboard")
                )

            if user["user_type"] == "company":

                return redirect(
                    url_for("company_dashboard")
                )

        flash(
            "Invalid email or password.",
            "danger"
        )

    return render_template(
        "login.html"
    )


@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(
        url_for("home")
    )


@app.route("/student/dashboard")
def student_dashboard():

    if (
        not login_required()
        or
        session.get("user_type") != "student"
    ):

        return redirect(
            url_for("login")
        )

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT *
        FROM students
        WHERE user_id=%s
        """,
        (
            session["user_id"],
        )
    )

    student = cursor.fetchone()

 
    cursor.execute("""
        SELECT internships.*, companies.company_name
        FROM internships
        JOIN companies
            ON internships.company_id = companies.id
        WHERE internships.status='Open'
        ORDER BY internships.id DESC
    """)

    internships = cursor.fetchall()

  
    cursor.execute("""
        SELECT
            applications.*,
            internships.title,
            companies.company_name
        FROM applications
        JOIN internships
            ON applications.internship_id = internships.id
        JOIN companies
            ON internships.company_id = companies.id
        WHERE applications.student_id=%s
        ORDER BY applications.id DESC
    """, (
        student["id"],
    ))

    applications = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "student_dashboard.html",
        student=student,
        internships=internships,
        applications=applications
    )



@app.route("/student/profile", methods=["GET", "POST"])
def student_profile():

    if not login_required() or session.get("user_type") != "student":
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor()

    if request.method == "POST":

        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        college = request.form.get("college", "").strip()
        degree = request.form.get("degree", "").strip()
        graduation_year = request.form.get("graduation_year", "").strip()
        skills = request.form.get("skills", "").strip()


        photo = request.files.get("photo")
        photo_path = None

        if photo and photo.filename:

            filename = secure_filename(photo.filename)

            if "." not in filename:
                flash("Invalid profile photo.", "danger")
                cursor.close()
                db.close()
                return redirect(url_for("student_profile", edit=1))

            extension = filename.rsplit(".", 1)[1].lower()

            if extension not in ALLOWED_IMAGE_EXTENSIONS:
                flash(
                    "Please upload JPG, JPEG, PNG or WEBP image.",
                    "danger"
                )
                cursor.close()
                db.close()
                return redirect(url_for("student_profile", edit=1))

            new_filename = f"student_{session['user_id']}.{extension}"

            photo.save(
                os.path.join(
                    PROFILE_FOLDER,
                    new_filename
                )
            )

            photo_path = f"uploads/profiles/{new_filename}"


        resume = request.files.get("resume")
        resume_path = None

        if resume and resume.filename:

            filename = secure_filename(resume.filename)

            if not allowed_resume(filename):
                flash(
                    "Please upload PDF, DOC or DOCX resume.",
                    "danger"
                )
                cursor.close()
                db.close()
                return redirect(url_for("student_profile", edit=1))

            extension = filename.rsplit(".", 1)[1].lower()

            new_filename = (
                f"student_{session['user_id']}_resume.{extension}"
            )

            resume.save(
                os.path.join(
                    RESUME_FOLDER,
                    new_filename
                )
            )

            resume_path = f"uploads/resumes/{new_filename}"


        if photo_path and resume_path:

            cursor.execute("""
                UPDATE students
                SET
                    full_name=%s,
                    phone=%s,
                    college=%s,
                    degree=%s,
                    graduation_year=%s,
                    skills=%s,
                    photo_path=%s,
                    resume_path=%s
                WHERE user_id=%s
            """, (
                full_name,
                phone,
                college,
                degree,
                graduation_year or None,
                skills,
                photo_path,
                resume_path,
                session["user_id"]
            ))

        elif photo_path:

            cursor.execute("""
                UPDATE students
                SET
                    full_name=%s,
                    phone=%s,
                    college=%s,
                    degree=%s,
                    graduation_year=%s,
                    skills=%s,
                    photo_path=%s
                WHERE user_id=%s
            """, (
                full_name,
                phone,
                college,
                degree,
                graduation_year or None,
                skills,
                photo_path,
                session["user_id"]
            ))

        elif resume_path:

            cursor.execute("""
                UPDATE students
                SET
                    full_name=%s,
                    phone=%s,
                    college=%s,
                    degree=%s,
                    graduation_year=%s,
                    skills=%s,
                    resume_path=%s
                WHERE user_id=%s
            """, (
                full_name,
                phone,
                college,
                degree,
                graduation_year or None,
                skills,
                resume_path,
                session["user_id"]
            ))

        else:

            cursor.execute("""
                UPDATE students
                SET
                    full_name=%s,
                    phone=%s,
                    college=%s,
                    degree=%s,
                    graduation_year=%s,
                    skills=%s
                WHERE user_id=%s
            """, (
                full_name,
                phone,
                college,
                degree,
                graduation_year or None,
                skills,
                session["user_id"]
            ))

        db.commit()

        session["name"] = full_name

        cursor.close()
        db.close()

        flash(
            "Profile updated successfully!",
            "success"
        )

        return redirect(url_for("student_profile"))


    cursor.execute("""
        SELECT *
        FROM students
        WHERE user_id=%s
    """, (
        session["user_id"],
    ))

    student = cursor.fetchone()

    cursor.close()
    db.close()

    edit_mode = request.args.get("edit") == "1"

    return render_template(
        "student_profile.html",
        student=student,
        edit_mode=edit_mode
    )


@app.route(
    "/apply/<int:internship_id>",
    methods=["POST"]
)
def apply_internship(
    internship_id
):

    if (
        not login_required()
        or
        session.get("user_type") != "student"
    ):

        return redirect(
            url_for("login")
        )

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT id
        FROM students
        WHERE user_id=%s
        """,
        (
            session["user_id"],
        )
    )

    student = cursor.fetchone()

    cursor.execute("""
        SELECT id
        FROM applications
        WHERE internship_id=%s
        AND student_id=%s
    """, (
        internship_id,
        student["id"]
    ))

    existing = cursor.fetchone()

    if existing:

        flash(
            "You already applied for this internship.",
            "warning"
        )

    else:

        cover_letter = request.form.get(
            "cover_letter",
            ""
        )

        cursor.execute("""
            INSERT INTO applications
            (
                internship_id,
                student_id,
                cover_letter,
                status
            )

            VALUES
            (
                %s,
                %s,
                %s,
                'Pending'
            )
        """, (
            internship_id,
            student["id"],
            cover_letter
        ))

        db.commit()

        flash(
            "Application submitted successfully.",
            "success"
        )

    cursor.close()
    db.close()

    return redirect(
        url_for("student_dashboard")
    )


@app.route(
    "/internship/<int:internship_id>"
)
def internship_details(
    internship_id
):

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            internships.*,
            companies.company_name,
            companies.description AS company_description

        FROM internships

        JOIN companies
            ON internships.company_id = companies.id

        WHERE internships.id=%s
    """, (
        internship_id,
    ))

    internship = cursor.fetchone()

    cursor.close()
    db.close()

    if not internship:

        flash(
            "Internship not found.",
            "danger"
        )

        return redirect(
            url_for("home")
        )

    return render_template(
        "internship_details.html",
        internship=internship
    )



@app.route("/company/dashboard")
def company_dashboard():

    if (
        not login_required()
        or
        session.get("user_type") != "company"
    ):

        return redirect(
            url_for("login")
        )

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT *
        FROM companies
        WHERE user_id=%s
        """,
        (
            session["user_id"],
        )
    )

    company = cursor.fetchone()

    cursor.execute("""
        SELECT *
        FROM internships
        WHERE company_id=%s
        ORDER BY id DESC
    """, (
        company["id"],
    ))

    internships = cursor.fetchall()

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM applications

        JOIN internships
            ON applications.internship_id = internships.id

        WHERE internships.company_id=%s
    """, (
        company["id"],
    ))

    application_count = cursor.fetchone()["total"]

    cursor.close()
    db.close()

    return render_template(
        "company_dashboard.html",
        company=company,
        internships=internships,
        application_count=application_count
    )


@app.route(
    "/company/profile",
    methods=["GET", "POST"]
)
def company_profile():

    if (
        not login_required()
        or
        session.get("user_type") != "company"
    ):

        return redirect(
            url_for("login")
        )

    db = get_db()
    cursor = db.cursor()

    if request.method == "POST":

        company_name = request.form[
            "company_name"
        ]

        industry = request.form[
            "industry"
        ]

        location = request.form[
            "location"
        ]

        website = request.form[
            "website"
        ]

        description = request.form[
            "description"
        ]

        cursor.execute("""
            UPDATE companies

            SET
                company_name=%s,
                industry=%s,
                location=%s,
                website=%s,
                description=%s

            WHERE user_id=%s
        """, (
            company_name,
            industry,
            location,
            website,
            description,
            session["user_id"]
        ))

        cursor.execute(
            """
            UPDATE users
            SET name=%s
            WHERE id=%s
            """,
            (
                company_name,
                session["user_id"]
            )
        )

        db.commit()

        session["name"] = company_name

        flash(
            "Company profile updated.",
            "success"
        )


    cursor.execute(
        """
        SELECT *
        FROM companies
        WHERE user_id=%s
        """,
        (
            session["user_id"],
        )
    )

    company = cursor.fetchone()

    cursor.close()
    db.close()

    return render_template(
        "company_profile.html",
        company=company
    )


@app.route(
    "/company/post",
    methods=["GET", "POST"]
)
def post_internship():

    if (
        not login_required()
        or
        session.get("user_type") != "company"
    ):

        return redirect(
            url_for("login")
        )

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT id
        FROM companies
        WHERE user_id=%s
        """,
        (
            session["user_id"],
        )
    )

    company = cursor.fetchone()

    if request.method == "POST":

        title = request.form[
            "title"
        ]

        description = request.form[
            "description"
        ]

        requirements = request.form[
            "requirements"
        ]

        skills = request.form[
            "skills"
        ]

        location = request.form[
            "location"
        ]

        stipend = request.form[
            "stipend"
        ]

        duration = request.form[
            "duration"
        ]

        deadline = request.form[
            "deadline"
        ]

        cursor.execute("""
            INSERT INTO internships
            (
                company_id,
                title,
                description,
                requirements,
                skills,
                location,
                stipend,
                duration,
                deadline,
                status
            )

            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                'Open'
            )
        """, (
            company["id"],
            title,
            description,
            requirements,
            skills,
            location,
            stipend,
            duration,
            deadline
        ))

        db.commit()

        cursor.close()
        db.close()

        flash(
            "Internship posted successfully.",
            "success"
        )

        return redirect(
            url_for("company_dashboard")
        )

    cursor.close()
    db.close()

    return render_template(
        "post_internship.html"
    )


@app.route(
    "/company/edit-internship/<int:internship_id>",
    methods=["GET", "POST"]
)
def edit_internship(internship_id):

    
    if (
        not login_required()
        or session.get("user_type") != "company"
    ):
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT id
        FROM companies
        WHERE user_id=%s
        """,
        (
            session["user_id"],
        )
    )

    company = cursor.fetchone()

    if not company:

        cursor.close()
        db.close()

        flash(
            "Company profile not found.",
            "danger"
        )

        return redirect(
            url_for("company_dashboard")
        )


    cursor.execute(
        """
        SELECT *
        FROM internships
        WHERE id=%s
        AND company_id=%s
        """,
        (
            internship_id,
            company["id"]
        )
    )

    internship = cursor.fetchone()

    if not internship:

        cursor.close()
        db.close()

        flash(
            "Internship not found.",
            "danger"
        )

        return redirect(
            url_for("company_dashboard")
        )


    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        requirements = request.form.get(
            "requirements",
            ""
        ).strip()

        skills = request.form.get(
            "skills",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        stipend = request.form.get(
            "stipend",
            ""
        ).strip()

        duration = request.form.get(
            "duration",
            ""
        ).strip()

        deadline = request.form.get(
            "deadline",
            ""
        ).strip()

        status = request.form.get(
            "status",
            "Open"
        ).strip()



        if not title or not description or not location or not duration:

            flash(
                "Please fill all required fields.",
                "danger"
            )

            cursor.close()
            db.close()

            return redirect(
                url_for(
                    "edit_internship",
                    internship_id=internship_id
                )
            )


        cursor.execute(
            """
            UPDATE internships

            SET
                title=%s,
                description=%s,
                requirements=%s,
                skills=%s,
                location=%s,
                stipend=%s,
                duration=%s,
                deadline=%s,
                status=%s

            WHERE id=%s
            AND company_id=%s
            """,
            (
                title,
                description,
                requirements,
                skills,
                location,
                stipend if stipend else None,
                duration,
                deadline if deadline else None,
                status,
                internship_id,
                company["id"]
            )
        )

        db.commit()

        cursor.close()
        db.close()

        flash(
            "Internship updated successfully!",
            "success"
        )

        return redirect(
            url_for("company_dashboard")
        )



    cursor.close()
    db.close()

    return render_template(
        "edit_internship.html",
        internship=internship
    )

@app.route("/company/applications")
def company_applications():

    if not login_required() or session.get("user_type") != "company":
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT id, company_name
        FROM companies
        WHERE user_id=%s
    """, (
        session["user_id"],
    ))

    company = cursor.fetchone()

    if not company:
        cursor.close()
        db.close()

        flash(
            "Company profile not found.",
            "danger"
        )

        return redirect(
            url_for("company_dashboard")
        )

    cursor.execute("""
        SELECT
            applications.*,

            students.full_name,
            students.phone,
            students.college,
            students.degree,
            students.graduation_year,
            students.skills,
            students.resume_path,
            students.photo_path,

            internships.title AS internship_title

        FROM applications

        JOIN students
            ON applications.student_id = students.id

        JOIN internships
            ON applications.internship_id = internships.id

        WHERE internships.company_id=%s

        ORDER BY applications.id DESC
    """, (
        company["id"],
    ))

    applications = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "company_applications.html",
        company=company,
        applications=applications
    )


@app.route(
    "/company/application/<int:application_id>/<status>",
    methods=["POST"]
)
def update_application(
    application_id,
    status
):

    if (
        not login_required()
        or
        session.get("user_type") != "company"
    ):

        return redirect(
            url_for("login")
        )

    allowed = [
        "Reviewed",
        "Shortlisted",
        "Accepted",
        "Rejected"
    ]

    if status not in allowed:

        flash(
            "Invalid application status.",
            "danger"
        )

        return redirect(
            url_for("company_applications")
        )

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        UPDATE applications

        SET status=%s

        WHERE id=%s

        AND internship_id IN (

            SELECT id
            FROM internships

            WHERE company_id=(
                SELECT id
                FROM companies
                WHERE user_id=%s
            )

        )
    """, (
        status,
        application_id,
        session["user_id"]
    ))

    db.commit()

    cursor.close()
    db.close()

    flash(
        "Application status updated.",
        "success"
    )

    return redirect(
        url_for("company_applications")
    )


@app.route("/search")
def search():

    keyword = request.args.get(
        "keyword",
        ""
    ).strip()

    location = request.args.get(
        "location",
        ""
    ).strip()

    db = get_db()
    cursor = db.cursor()

    query = """
        SELECT
            internships.*,
            companies.company_name

        FROM internships

        JOIN companies
            ON internships.company_id = companies.id

        WHERE internships.status = 'Open'
    """

    params = []


    if keyword:

        keyword_lower = keyword.lower()

        
        if keyword_lower in [
            "intern",
            "internship",
            "internships"
        ]:

            pass

        else:

            query += """
                AND (
                    LOWER(internships.title)
                        LIKE LOWER(%s)

                    OR LOWER(internships.skills)
                        LIKE LOWER(%s)

                    OR LOWER(companies.company_name)
                        LIKE LOWER(%s)

                    OR LOWER(internships.description)
                        LIKE LOWER(%s)

                    OR LOWER(internships.location)
                        LIKE LOWER(%s)
                )
            """

            word = "%" + keyword + "%"

            params.extend([
                word,
                word,
                word,
                word,
                word
            ])


    if location:

        query += """
            AND LOWER(internships.location)
                LIKE LOWER(%s)
        """

        params.append(
            "%" + location + "%"
        )


    query += """
        ORDER BY internships.id DESC
    """

    cursor.execute(
        query,
        tuple(params)
    )

    internships = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "search.html",
        internships=internships,
        keyword=keyword,
        location=location
    )

@app.route("/admin")
def admin_dashboard():

    if not admin_required():
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT id, name, email, user_type
        FROM users
        ORDER BY id DESC
    """)
    users = cursor.fetchall()
    cursor.execute("""
        SELECT *
        FROM students
        ORDER BY id DESC
    """)
    students = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM companies
        ORDER BY id DESC
    """)
    companies = cursor.fetchall()

    cursor.execute("""
        SELECT internships.*, companies.company_name
        FROM internships
        JOIN companies
        ON internships.company_id = companies.id
        ORDER BY internships.id DESC
    """)
    internships = cursor.fetchall()

    cursor.execute("""
        SELECT applications.*
        FROM applications
        ORDER BY applications.id DESC
    """)
    applications = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "admin_dashboard.html",
        users=users,
        students=students,
        companies=companies,
        internships=internships,
        applications=applications
    )
if __name__ == "__main__":

    app.run(
        debug=True
    )