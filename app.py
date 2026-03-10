from flask import Flask, render_template, request, redirect, session
import psycopg2
import os
from dotenv import load_dotenv
from flask import flash

load_dotenv()

app = Flask(__name__)
app.secret_key = "auction_secret"

DATABASE_URL = os.getenv("DATABASE_URL")


def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


# ---------------- DATABASE SETUP ----------------

def create_tables():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT,
        team_name TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS teams(
        id SERIAL PRIMARY KEY,
        team_name TEXT UNIQUE,
        purse INT DEFAULT 10000000
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS players(
        id SERIAL PRIMARY KEY,
        name TEXT,
        runs INT,
        wickets INT,
        bat_avg FLOAT,
        bowl_avg FLOAT,
        team TEXT DEFAULT 'Unsold',
        base_price INT DEFAULT 50000,
        current_bid INT DEFAULT 0,
        last_bid_team TEXT
    )
    """)

    conn.commit()
    cur.close()
    conn.close()


def insert_teams():

    conn = get_db()
    cur = conn.cursor()

    teams = ["CSK","MI","RCB","KKR","SRH","DC" ,"RR","PBKS","LSG","GT"]

    for t in teams:
        cur.execute(
            "INSERT INTO teams(team_name) VALUES(%s) ON CONFLICT DO NOTHING",
            (t,)
        )

    conn.commit()
    cur.close()
    conn.close()


# ---------------- HOME ----------------

@app.route("/")
def index():

    if "user" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT id,name,runs,wickets,bat_avg,bowl_avg,team,base_price,current_bid
    FROM players
    ORDER BY id
    """)

    players = cur.fetchall()

    purse = 0

    if session["role"] == "user":
        cur.execute(
            "SELECT purse FROM teams WHERE team_name=%s",
            (session["team"],)
        )
        purse = cur.fetchone()[0]

    cur.close()
    conn.close()

    return render_template(
        "index.html",
        players=players,
        username=session["user"],
        role=session["role"],
        team=session.get("team"),
        purse=purse
    )

# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET","POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        team = request.form["team"]

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT * FROM users WHERE email=%s",(email,))
        if cur.fetchone():
            return "Email already exists."
        
        role = request.form.get("role")
        
        cur.execute(
        "INSERT INTO users(name,email,password,role,team_name) VALUES(%s,%s,%s,%s,%s)",
        (name,email,password,role,team)
        )

        conn.commit()

        cur.close()
        conn.close()

        return redirect("/login")

    return render_template("register.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
        SELECT name,role,team_name
        FROM users
        WHERE email=%s AND password=%s
        """,(email,password))

        user = cur.fetchone()

        cur.close()
        conn.close()

        if user:
            session["user"] = user[0]
            session["role"] = user[1]
            session["team"] = user[2]

            return redirect("/")

    return render_template("login.html")


# ---------------- ADD PLAYER ----------------

@app.route("/add_player", methods=["POST"])
def add_player():

    if session["role"] != "admin":
        return redirect("/")

    name = request.form["name"]
    runs = request.form["runs"]
    wickets = request.form["wickets"]
    bat_avg = request.form["bat_avg"]
    bowl_avg = request.form["bowl_avg"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO players(name,runs,wickets,bat_avg,bowl_avg)
    VALUES(%s,%s,%s,%s,%s)
    """,(name,runs,wickets,bat_avg,bowl_avg))

    conn.commit()

    cur.close()
    conn.close()

    return redirect("/")



@app.route("/sell/<int:player_id>", methods=["POST"])
def sell(player_id):

    if session["role"] != "admin":
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    UPDATE players
    SET team = last_bid_team
    WHERE id=%s
    """,(player_id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/")


# ---------------- BID SYSTEM ----------------

@app.route("/bid/<int:player_id>", methods=["POST"])
def bid(player_id):

    if "team" not in session:
        return redirect("/login")

    team = session["team"]
    bid_price = int(request.form["price"])

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT current_bid,base_price,last_bid_team
    FROM players
    WHERE id=%s
    """,(player_id,))

    player = cur.fetchone()

    current_bid = player[0]
    base_price = player[1]
    last_team = player[2]

    if current_bid == 0 and bid_price < base_price:
        flash("⚠️ Bid must be higher than base price.", "error")
        return redirect("/")

    if bid_price <= current_bid:
        flash("⚠️ Bid must be higher than current bid.", "error")
        return redirect("/")

    if last_team == team:
        flash("⚠️ Bid must be placed by another team first.", "error")
        return redirect("/")

    cur.execute(
        "SELECT purse FROM teams WHERE team_name=%s",
        (team,)
    )

    purse = cur.fetchone()[0]

    diff = bid_price - current_bid

    if diff > purse:
        flash("💰 Your team purse is not enough for this bid.", "error")
        return redirect("/")

    cur.execute("""
    UPDATE players
    SET current_bid=%s,
        team=%s,
        last_bid_team=%s
    WHERE id=%s
    """,(bid_price,team,team,player_id))

    cur.execute("""
    UPDATE teams
    SET purse = purse - %s
    WHERE team_name=%s
    """,(diff,team))

    conn.commit()

    cur.close()
    conn.close()

    return redirect("/")

@app.route("/reset_auction", methods=["POST"])
def reset_auction():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE players
        SET team=NULL,
            current_bid=base_price
    """)

    conn.commit()
    cur.close()
    conn.close()

    flash("Auction has been reset successfully.", "success")
    return redirect("/")

@app.route("/reset_player/<int:player_id>", methods=["POST"])
def reset_player(player_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE players
        SET team=NULL,
            current_bid=base_price
        WHERE id=%s
    """,(player_id,))

    conn.commit()
    cur.close()
    conn.close()

    flash("Player auction reset.", "success")
    return redirect("/")

# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------------- START APP ----------------

if __name__ == "__main__":

    create_tables()
    insert_teams()

    app.run(debug=True)