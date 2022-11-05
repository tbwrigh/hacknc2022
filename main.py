import sqlite3

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi import FastAPI, Form

from typing import Union

templates = Jinja2Templates(directory="templates")

con = sqlite3.connect("user.db")
cur = con.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
	username TEXT PRIMARY KEY, 
	email TEXT NOT NULL UNIQUE,
    password_hash TEXT,
    firstname TEXT,
    lastname TEXT,
    profile_image_path TEXT DEFAULT 'default.png'
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS posts (
	id INTEGER PRIMARY KEY,
	caption TEXT NOT NULL,
    video_paths TEXT,
    usernames TEXT,
    timestamp TEXT
);
""")

con.commit()

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return RedirectResponse("/static/login.html")

@app.post("/login/")
def login(username: str = Form(), password: str = Form()):
    res = cur.execute(f"SELECT password FROM users WHERE username='{username}'")
    res.fetchall()

    if (len(res) != 0):
        if res[0][0] == password:
            print("Correct Password")
        else:
            print("Your Password is Incorrect")
    else:
        print("Your Username is Invalid")
        # user not found or doesnt meet requirments
    
@app.post("/new_user/") #check if username or email is in system before adding to user
def new_user(firstname: str= Form(), lastname: str= Form(), username: str = Form(), email: str = Form(), password: str = Form()):
    #adds to a table    return {"username": username}
    

    cur.execute(f"""
        INSERT INTO users VALUES ({username}, {email}, {password}, {firstname}, {lastname})
    """)
    #saves it 
    con.commit()

    return {"username": username}