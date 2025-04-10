from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector

app = Flask(__name__)
app.secret_key = 'secretkey123'  # using session

# connect MySQL
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="groot",
    database="sportcon_v2", # change name of database
    port=3306
)
def get_cursor():
    global conn
    if not conn.is_connected():
        conn.reconnect()
    return conn.cursor(dictionary=True)

cursor = conn.cursor(dictionary=True)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/home")
def home():
    return render_template("home.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        last_name = request.form["last_name"]
        first_name = request.form["first_name"]
        gender = request.form["gender"]
        age = request.form["age"]
        sport = request.form["sport"]

        if password != confirm_password:
            return "Passwords do not match!"

        # Insert user info into 'users' table
        cursor.execute("""
            INSERT INTO users (email, password_hash, first_name, last_name, gender, age)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (email, password, first_name, last_name, gender, age))
        conn.commit()

        # Get user_id
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        user_id = cursor.fetchone()["id"]

        # Get sport_id from 'sports' table
        cursor.execute("SELECT id FROM sports WHERE name = %s", (sport,))
        sport_result = cursor.fetchone()

        if sport_result:
            sport_id = sport_result["id"]
            cursor.execute("INSERT INTO user_sports (user_id, sport_id) VALUES (%s, %s)", (user_id, sport_id))
            conn.commit()

        return redirect("/")  # Redirect to login page

    cursor.execute("SELECT name FROM sports")
    sports = cursor.fetchall()
    return render_template("register.html", sports=sports)

@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"]
    password = request.form["password"]

    cursor.execute("SELECT * FROM users WHERE email = %s AND password_hash = %s", (email, password))
    user = cursor.fetchone()

    if user:
        session["user_id"] = user["id"]
        return redirect("/user")
    else:
        return "Login failed!"

@app.route("/user")
def user_page():
    if "user_id" not in session:
        return redirect("/")

    cursor = get_cursor()
    cursor.execute("""
        SELECT posts.content, posts.created_at, users.first_name, users.last_name
        FROM posts
        JOIN users ON posts.user_id = users.id
        ORDER BY posts.created_at DESC
    """)
    posts = cursor.fetchall()

    return render_template("user.html", posts=posts)


@app.route("/profile")
def profile():
    return render_template("profile.html")

@app.route("/setting")
def settings():
    return render_template("setting.html")

@app.route("/events")
def events():
    return render_template("appointment.html")

@app.route("/chat/<int:receiver_id>", methods=["GET", "POST"])
def chat(receiver_id):
    if "user_id" not in session:
        return redirect(url_for("index"))

    sender_id = session["user_id"]

    if request.method == "POST":
        message = request.form["message"]
        cursor.execute("""
            INSERT INTO messages (sender_id, receiver_id, content)
            VALUES (%s, %s, %s)
        """, (sender_id, receiver_id, message))
        conn.commit()
        return redirect(url_for("chat", receiver_id=receiver_id))

    cursor.execute("""
        SELECT * FROM messages
        WHERE (sender_id = %s AND receiver_id = %s)
           OR (sender_id = %s AND receiver_id = %s)
        ORDER BY created_at ASC
    """, (sender_id, receiver_id, receiver_id, sender_id))
    messages = cursor.fetchall()

    cursor.execute("SELECT first_name FROM users WHERE id = %s", (receiver_id,))
    receiver = cursor.fetchone()

    return render_template("chat.html", messages=messages, receiver=receiver)

@app.route("/find", methods=["GET", "POST"])
def find():
    if "user_id" not in session:
        return redirect("/")

    result = None
    if request.method == "POST":
        keyword = request.form["keyword"]

        # find by user name or email
        cursor.execute("""
            SELECT * FROM users
            WHERE (first_name LIKE %s OR email LIKE %s)
              AND id != %s
        """, (f"%{keyword}%", f"%{keyword}%", session["user_id"]))
        result = cursor.fetchone()

    return render_template("Find.html", result=result)

@app.route("/send_request/<int:receiver_id>")
def send_request(receiver_id):
    if "user_id" not in session:
        return redirect("/")

    cursor.execute("""
        INSERT INTO friend_requests (sender_id, receiver_id)
        VALUES (%s, %s)
    """, (session["user_id"], receiver_id))
    conn.commit()
    return redirect("/find")


@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/notifications")
def notifications():
    if 'user_id' not in session:
        return redirect(url_for("index"))

    user_id = session['user_id']
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT fr.id, u.first_name AS sender_name
        FROM friend_requests fr
        JOIN users u ON fr.sender_id = u.id
        WHERE fr.receiver_id = %s AND fr.status = 'pending'
    """, (user_id,))
    requests = cursor.fetchall()
    return render_template("notifications.html", requests=requests)

@app.route("/handle_request/<int:request_id>/<action>", methods=["POST"])
def handle_request(request_id, action):
    if 'user_id' not in session:
        return redirect(url_for("index"))

    if action not in ['accept', 'reject']:
        return "Invalid action", 400

    new_status = 'accepted' if action == 'accept' else 'rejected'
    cursor = conn.cursor()
    cursor.execute("UPDATE friend_requests SET status = %s WHERE id = %s", (new_status, request_id))
    conn.commit()
    return redirect(url_for("notifications"))

@app.route("/chatlist")
def chatlist():
    if "user_id" not in session:
        return redirect("/")

    user_id = session["user_id"]

    # friend list
    cursor.execute("""
        SELECT u.id, u.first_name, u.last_name
        FROM users u
        JOIN friend_requests fr
          ON ((fr.sender_id = u.id AND fr.receiver_id = %s)
           OR (fr.receiver_id = u.id AND fr.sender_id = %s))
        WHERE fr.status = 'accepted' AND u.id != %s
    """, (user_id, user_id, user_id))
    friends = cursor.fetchall()

    # chat list
    cursor.execute("""
        SELECT u.id, u.first_name, u.last_name, MAX(m.created_at) as last_msg_time
        FROM users u
        JOIN messages m ON (m.sender_id = u.id OR m.receiver_id = u.id)
        WHERE (m.sender_id = %s OR m.receiver_id = %s)
         AND u.id != %s
        GROUP BY u.id, u.first_name, u.last_name
        ORDER BY last_msg_time DESC

    """, (user_id, user_id, user_id))
    recent_chats = cursor.fetchall()

    return render_template("chatlist.html", friends=friends, recent_chats=recent_chats)

import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/create_post', methods=['POST'])
def create_post():
    if "user_id" not in session:
        return redirect(url_for("index"))

    user_id = session.get('user_id')
    content = request.form['content']
    media_file = request.files.get('media')

    media_url = None
    media_type = None

    if media_file and allowed_file(media_file.filename):
        filename = secure_filename(media_file.filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        media_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        media_file.save(media_path)
        media_url = f'{filename}'
        ext = filename.rsplit('.', 1)[1].lower()
        media_type = 'image' if ext in ['png', 'jpg', 'jpeg', 'gif'] else 'video'

    cursor = get_cursor()
    cursor.execute("""
        INSERT INTO posts (user_id, content, media_url, media_type)
        VALUES (%s, %s, %s, %s)
    """, (user_id, content, media_url, media_type))
    conn.commit()

    return redirect(url_for('user_page'))  


    cursor.execute("""
    SELECT posts.content, posts.created_at, posts.media_url, posts.media_type, users.first_name, users.last_name
    FROM posts
    JOIN users ON posts.user_id = users.id
    ORDER BY posts.created_at DESC
""")
if __name__ == "__main__":
    app.run(debug=True)