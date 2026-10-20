import os
from functools import wraps
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    session,
    flash,
)
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt

from chatbot.response_engine import get_answer
from chatbot.nlp_analysis import analyze_message
from chatbot.phishing_detector import check_url


# =====================================================
# APPLICATION CONFIGURATION
# =====================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY")

if not app.config["SECRET_KEY"]:
    raise RuntimeError(
        "Set the FLASK_SECRET_KEY environment variable before starting Flask."
    )

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("COOKIE_SECURE", "false").lower() == "true"
)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)

app.config["MYSQL_HOST"] = os.environ.get("MYSQL_HOST", "localhost")
app.config["MYSQL_PORT"] = int(os.environ.get("MYSQL_PORT", "3306"))
app.config["MYSQL_USER"] = os.environ.get("MYSQL_USER", "root")
app.config["MYSQL_PASSWORD"] = os.environ.get("MYSQL_PASSWORD", "")
app.config["MYSQL_DB"] = os.environ.get("MYSQL_DB", "defaultdb")
app.config["MYSQL_CURSORCLASS"] = "DictCursor"
app.config["MYSQL_CUSTOM_OPTIONS"] = {"ssl": {}}
mysql = MySQL(app)
bcrypt = Bcrypt(app)


# =====================================================
# DATABASE INITIALIZATION
# =====================================================

_tables_initialized = False


def initialize_chat_tables():
    cursor = mysql.connection.cursor()

    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                chat_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                chat_title VARCHAR(200) NOT NULL DEFAULT 'New Chat',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_chat_user (user_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
                    ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                message_id INT AUTO_INCREMENT PRIMARY KEY,
                chat_id INT NOT NULL,
                sender ENUM('user', 'bot') NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_message_chat (chat_id),
                FOREIGN KEY (chat_id) REFERENCES chat_sessions(chat_id)
                    ON DELETE CASCADE
            )
            """
        )

        mysql.connection.commit()

    except Exception:
        mysql.connection.rollback()
        app.logger.exception("Could not initialize chat tables")
        raise

    finally:
        cursor.close()


@app.before_request
def ensure_chat_tables():
    global _tables_initialized

    if not _tables_initialized:
        initialize_chat_tables()
        _tables_initialized = True


# =====================================================
# AUTHENTICATION HELPERS
# =====================================================

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({
                    "error": "Please log in first."
                }), 401

            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped_view


def get_owned_chat(cursor, chat_id):
    """Return a chat only when it belongs to the logged-in user."""
    cursor.execute(
        """
        SELECT chat_id, chat_title
        FROM chat_sessions
        WHERE chat_id = %s AND user_id = %s
        """,
        (chat_id, session["user_id"]),
    )

    return cursor.fetchone()


# =====================================================
# HOME / DASHBOARD
# =====================================================

@app.route("/")
@login_required
def home():
    cursor = mysql.connection.cursor()

    try:
        cursor.execute(
            """
            SELECT user_id, name, email, created_at
            FROM users
            WHERE user_id = %s
            """,
            (session["user_id"],),
        )

        user = cursor.fetchone()

        if not user:
            session.clear()
            return redirect(url_for("login"))

        return render_template("index.html", user=user)

    except Exception:
        app.logger.exception("Failed to load user dashboard")
        return "Unable to load dashboard. Please try again.", 500

    finally:
        cursor.close()
@app.route("/settings")
@login_required
def settings_page():
    cursor = mysql.connection.cursor()
    try:
        cursor.execute(
            """
            SELECT user_id, name, email, created_at
            FROM users
            WHERE user_id = %s
            """,
            (session["user_id"],)
        )
        user = cursor.fetchone()

        if not user:
            return redirect(url_for("login"))

        return render_template("settings.html", user=user)
    finally:
        cursor.close()


# =====================================================
# REGISTER
# =====================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Please fill in all fields.", "error")
            return render_template("register.html")

        if len(name) > 100 or len(email) > 150:
            flash("Name or email is too long.", "error")
            return render_template("register.html")

        if len(password) < 8:
            flash(
                "Password must contain at least 8 characters.",
                "error",
            )
            return render_template("register.html")

        cursor = mysql.connection.cursor()

        try:
            cursor.execute(
                "SELECT user_id FROM users WHERE email = %s",
                (email,),
            )

            if cursor.fetchone():
                flash(
                    "Unable to register with those details.",
                    "error",
                )
                return render_template("register.html")

            password_hash = bcrypt.generate_password_hash(
                password
            ).decode("utf-8")

            cursor.execute(
                """
                INSERT INTO users (name, email, password_hash)
                VALUES (%s, %s, %s)
                """,
                (name, email, password_hash),
            )

            mysql.connection.commit()

            flash(
                "Account created successfully. Please log in.",
                "success",
            )
            return redirect(url_for("login"))

        except Exception:
            mysql.connection.rollback()
            app.logger.exception("Registration failed")
            flash("Registration failed. Please try again.", "error")

        finally:
            cursor.close()

    return render_template("register.html")


# =====================================================
# LOGIN
# =====================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        cursor = mysql.connection.cursor()

        try:
            cursor.execute(
                """
                SELECT user_id, name, email, password_hash
                FROM users
                WHERE email = %s
                """,
                (email,),
            )

            user = cursor.fetchone()

            if user and bcrypt.check_password_hash(
                user["password_hash"], password
            ):
                session.clear()
                session.permanent = True
                session["user_id"] = user["user_id"]
                session["user_name"] = user["name"]

                return redirect(url_for("home"))

            flash("Invalid email or password.", "error")

        except Exception:
            app.logger.exception("Login failed")
            flash("Unable to log in right now.", "error")

        finally:
            cursor.close()

    return render_template("login.html")


# =====================================================
# LOGOUT
# =====================================================

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


# =====================================================
# USER PROFILE
# =====================================================

@app.route("/api/profile", methods=["GET", "PUT"])
@login_required
def profile():
    cursor = mysql.connection.cursor()

    try:
        if request.method == "GET":
            cursor.execute(
                """
                SELECT user_id, name, email, created_at
                FROM users
                WHERE user_id = %s
                """,
                (session["user_id"],),
            )

            user = cursor.fetchone()

            if not user:
                session.clear()
                return jsonify({"error": "User not found."}), 404

            return jsonify(user)

        data = request.get_json(silent=True) or {}

        name = data.get("name", "").strip()
        email = data.get("email", "").strip().lower()

        if (
            not isinstance(name, str)
            or not isinstance(email, str)
            or not name
            or not email
            or len(name) > 100
            or len(email) > 150
        ):
            return jsonify({
                "error": "Enter a valid name and email."
            }), 400

        cursor.execute(
            """
            SELECT user_id
            FROM users
            WHERE email = %s AND user_id != %s
            """,
            (email, session["user_id"]),
        )

        if cursor.fetchone():
            return jsonify({
                "error": "Email is already in use."
            }), 409

        cursor.execute(
            """
            UPDATE users
            SET name = %s, email = %s
            WHERE user_id = %s
            """,
            (name, email, session["user_id"]),
        )

        mysql.connection.commit()
        session["user_name"] = name

        return jsonify({
            "message": "Profile updated successfully."
        })

    except Exception:
        mysql.connection.rollback()
        app.logger.exception("Profile request failed")

        return jsonify({
            "error": "Unable to process profile request."
        }), 500

    finally:
        cursor.close()




# =====================================================
# CHANGE PASSWORD
# =====================================================

@app.route("/api/change-password", methods=["POST"])
@login_required
def change_password():
    data = request.get_json(silent=True) or {}

    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if (
        not isinstance(current_password, str)
        or not isinstance(new_password, str)
    ):
        return jsonify({"error": "Invalid password input."}), 400

    if len(new_password) < 8:
        return jsonify({
            "error": "New password must contain at least 8 characters."
        }), 400

    cursor = mysql.connection.cursor()

    try:
        cursor.execute(
            """
            SELECT password_hash
            FROM users
            WHERE user_id = %s
            """,
            (session["user_id"],),
        )

        user = cursor.fetchone()

        if not user or not bcrypt.check_password_hash(
            user["password_hash"], current_password
        ):
            return jsonify({
                "error": "Current password is incorrect."
            }), 400

        new_hash = bcrypt.generate_password_hash(
            new_password
        ).decode("utf-8")

        cursor.execute(
            """
            UPDATE users
            SET password_hash = %s
            WHERE user_id = %s
            """,
            (new_hash, session["user_id"]),
        )

        mysql.connection.commit()

        session.clear()

        return jsonify({
            "message": "Password changed. Please log in again.",
            "redirect": url_for("login"),
        })

    except Exception:
        mysql.connection.rollback()
        app.logger.exception("Password change failed")

        return jsonify({
            "error": "Unable to change password."
        }), 500

    finally:
        cursor.close()


# =====================================================
# CHAT LIST AND CREATE CHAT
# =====================================================

@app.route("/api/chats", methods=["GET", "POST"])
@login_required
def chats():
    cursor = mysql.connection.cursor()

    try:
        if request.method == "GET":
            cursor.execute(
                """
                SELECT chat_id, chat_title, created_at, updated_at
                FROM chat_sessions
                WHERE user_id = %s
                ORDER BY updated_at DESC
                """,
                (session["user_id"],),
            )

            return jsonify({"chats": cursor.fetchall()})

        cursor.execute(
            """
            INSERT INTO chat_sessions (user_id, chat_title)
            VALUES (%s, %s)
            """,
            (session["user_id"], "New Chat"),
        )

        chat_id = cursor.lastrowid
        mysql.connection.commit()

        return jsonify({
            "chat_id": chat_id,
            "chat_title": "New Chat",
        }), 201

    except Exception:
        mysql.connection.rollback()
        app.logger.exception("Chat session request failed")

        return jsonify({
            "error": "Unable to process chats."
        }), 500

    finally:
        cursor.close()


# =====================================================
# OPEN OR DELETE A CHAT
# =====================================================

@app.route(
    "/api/chats/<int:chat_id>",
    methods=["GET", "DELETE"],
)
@login_required
def chat_details(chat_id):
    cursor = mysql.connection.cursor()

    try:
        chat = get_owned_chat(cursor, chat_id)

        if not chat:
            return jsonify({"error": "Chat not found."}), 404

        if request.method == "DELETE":
            cursor.execute(
                """
                DELETE FROM chat_sessions
                WHERE chat_id = %s AND user_id = %s
                """,
                (chat_id, session["user_id"]),
            )

            mysql.connection.commit()

            return jsonify({"message": "Chat deleted."})

        cursor.execute(
            """
            SELECT sender, message, created_at
            FROM chat_messages
            WHERE chat_id = %s
            ORDER BY message_id ASC
            """,
            (chat_id,),
        )

        return jsonify({
            "chat": chat,
            "messages": cursor.fetchall(),
        })

    except Exception:
        mysql.connection.rollback()
        app.logger.exception("Chat detail request failed")

        return jsonify({
            "error": "Unable to load this chat."
        }), 500

    finally:
        cursor.close()


# =====================================================
# GEMINI CHAT API
# =====================================================

@app.route("/api/chat", methods=["POST"])
@login_required
def chat():
    data = request.get_json(silent=True) or {}

    message = data.get("message", "")
    history = data.get("history", [])
    chat_id = data.get("chat_id")

    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Please enter a message."}), 400

    message = message.strip()

    if len(message) > 10000:
        return jsonify({"error": "Message is too long."}), 400

    if not isinstance(history, list):
        return jsonify({
            "error": "Invalid conversation history."
        }), 400

    history = [
        item
        for item in history[-8:]
        if isinstance(item, dict)
    ]

    cursor = mysql.connection.cursor()
    created_chat = False

    try:
        if chat_id is not None:
            # Reject invalid chat IDs.
            if not isinstance(chat_id, int) or isinstance(chat_id, bool):
                return jsonify({"error": "Invalid chat ID."}), 400

            # A user can only continue their own chat.
            existing_chat = get_owned_chat(cursor, chat_id)

            if not existing_chat:
                return jsonify({"error": "Chat not found."}), 404

        else:
            # Create a chat for the currently logged-in user.
            cursor.execute(
                """
                INSERT INTO chat_sessions (user_id, chat_title)
                VALUES (%s, %s)
                """,
                (session["user_id"], "New Chat"),
            )

            chat_id = cursor.lastrowid
            created_chat = True

        # Save the user's message.
        cursor.execute(
            """
            INSERT INTO chat_messages (chat_id, sender, message)
            VALUES (%s, 'user', %s)
            """,
            (chat_id, message),
        )

        # Set a title from the first message if the chat
        # has not received a meaningful title yet.
        cursor.execute(
            """
            SELECT chat_title
            FROM chat_sessions
            WHERE chat_id = %s AND user_id = %s
            """,
            (chat_id, session["user_id"]),
        )

        existing_chat = cursor.fetchone()

        if existing_chat and (
            created_chat
            or existing_chat["chat_title"] == "New Chat"
        ):
            title = message[:60].strip() or "New Chat"

            cursor.execute(
                """
                UPDATE chat_sessions
                SET chat_title = %s
                WHERE chat_id = %s AND user_id = %s
                """,
                (title, chat_id, session["user_id"]),
            )

        mysql.connection.commit()

    except Exception:
        mysql.connection.rollback()
        app.logger.exception("Could not save user message")

        return jsonify({
            "error": "Unable to save your message."
        }), 500

    finally:
        cursor.close()

    # Generate the Gemini response.
    try:
        answer = get_answer(
            user_message=message,
            conversation_history=history,
        )

        if not isinstance(answer, str):
            answer = str(answer)

    except Exception:
        app.logger.exception("Chatbot response failed")

        return jsonify({
            "error": "Unable to generate a response. Your message was saved.",
            "chat_id": chat_id,
        }), 500

    # Save the bot response only if the chat belongs to this user.
    cursor = mysql.connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO chat_messages (chat_id, sender, message)
            SELECT %s, 'bot', %s
            FROM chat_sessions
            WHERE chat_id = %s AND user_id = %s
            """,
            (
                chat_id,
                answer,
                chat_id,
                session["user_id"],
            ),
        )

        if cursor.rowcount != 1:
            mysql.connection.rollback()

            return jsonify({
                "error": "Chat not found.",
            }), 404

        mysql.connection.commit()

    except Exception:
        mysql.connection.rollback()
        app.logger.exception("Could not save bot response")

        return jsonify({
            "error": "Response generated but could not be saved.",
            "answer": answer,
            "chat_id": chat_id,
        }), 500

    finally:
        cursor.close()

    message_analysis = analyze_message(message)

    return jsonify({
        "answer": answer,
        "chat_id": chat_id,
        "analysis": message_analysis,
    })


@app.route("/api/check-url", methods=["POST"])
@login_required
def check_url_api():
    """Classify a URL using the trained phishing model."""
    data = request.get_json(silent=True) or {}
    url = data.get("url", "")
    if not isinstance(url, str):
        return jsonify({"ok": False, "error": "URL must be a string."}), 400
    result = check_url(url)
    return jsonify(result), (200 if result.get("ok") else 400)


# =====================================================
# ANALYTICS API
# =====================================================

@app.route("/api/analytics", methods=["GET"])
@login_required
def analytics():
    cursor = mysql.connection.cursor()

    try:
        user_id = session["user_id"]

        cursor.execute(
            """
            SELECT COUNT(*) AS total_conversations
            FROM chat_sessions
            WHERE user_id = %s
            """,
            (user_id,),
        )
        conversations = cursor.fetchone()

        cursor.execute(
            """
            SELECT COUNT(*) AS total_responses
            FROM chat_messages AS cm
            INNER JOIN chat_sessions AS cs
                ON cm.chat_id = cs.chat_id
            WHERE cs.user_id = %s
                AND cm.sender = 'bot'
            """,
            (user_id,),
        )
        responses = cursor.fetchone()

        return jsonify({
            "conversations": conversations["total_conversations"],
            "responses": responses["total_responses"],
        })

    except Exception:
        app.logger.exception("Failed to load analytics")
        return jsonify({
            "error": "Unable to load analytics."
        }), 500

    finally:
        cursor.close()


# =====================================================
# RUN APPLICATION
# =====================================================

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False,
    )
