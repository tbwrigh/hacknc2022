import sqlite3
import hashlib 
import uuid
import random
import time

from fastapi import FastAPI, Form, File, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse

from typing import Union, Optional

from hashlib import sha256

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
    timestamp TEXT,
    next_user TEXT,
    users_remaining TEXT,
    time_limit INT,
    likes INT DEFAULT 0,
    comments TEXT DEFAULT ''
);
""")

con.commit()

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

login_hashes = []

@app.get("/")
def read_root():
    return RedirectResponse("/static/login.html")

@app.post("/login/")
def login(username: str = Form(), password: str = Form(), timestamp: str = Form()):
    res = cur.execute(f"SELECT password FROM users WHERE username='{username}'")
    res.fetchall()

    if (len(res) != 0):
        if res[0][0] == password:
            full_hash = password + '|' + timestamp 
            hashed_string = hashlib.sha256(full_hash.encode('utf-8')).hexdigest()
            hashed_string = username + '|' + hashed_string
            login_hashes.append(hashed_string)

            return RedirectResponse("/userhome?auth={hashed_string}")
            # success
        else:
            return RedirectResponse("/static/login.html?error=badpass")
            #bad password
    else:
        return RedirectResponse("/static/login.html?error=badname")
        # bad username
    
@app.post("/new_user/") #check if username or email is in system before adding to user
def new_user(firstname: str= Form(), lastname: str= Form(), username: str = Form(), email: str = Form(), password: str = Form(), timestamp: str = Form()):
    res = cur.execute(f"SELECT email FROM users WHERE email='{email}'")
    res.fetchall()

    if (len(res) != 0):
        print("Error email already has account")

    res = cur.execute(f"SELECT username FROM users WHERE username='{username}'")
    res.fetchall()

    if (len(res) != 0):
        print("Error email already ascoiated with a account")
    
    cur.execute(f"""
        INSERT INTO users VALUES ({username}, {email}, {password}, {firstname}, {lastname})
    """)
    #saves it 
    con.commit()

    full_hash = password + '|' + timestamp 
    hashed_string = hashlib.sha256(full_hash.encode('utf-8')).hexdigest()
    hashed_string = username + '|' + hashed_string
    login_hashes.append(hashed_string)
    
    return RedirectResponse("/userhome?auth={hashed_string}")
    #newuser


@app.post("/profile_pic/")
def UploadImage(file: bytes = File(), fileb: UploadFile = File()):
    filename = str(uuid.uuid4())
    
    res = cur.execute(f"SELECT profile_image_path FROM users WHERE profile_image_path='{filename}'")
    res.fetchall()

    if (len(res) != 0):
        print("Error filename already in database")

    extension = str(fileb.filename).split(".")[-1]

    if extension != "png" or extension != "jpg":
        print("wrong file type")

    with open(f'./static/images/{filename}.{extension}', 'wb') as image:
        image.write(file)
        image.close()

    return 'got it'

@app.post("/logout/")
def logout(hashed_string: str = Form()):
    if login_hashes.find(hashed_string) != -1:
        login_hashes.remove(hashed_string)
    return RedirectResponse("/static/login.html")

@app.post("/new_post/")
def NewPost(file: bytes = File(), fileb: UploadFile = File(), authstring: str = Form(), caption: str = Form(), next_user: str = Form(), chain_length: str = Form(), max_time: int = Form()):
    #take in parameters for files, authstring, and caption
    res = cur.execute(f"SELECT id FROM posts'")
    res.fetchall()
    if len(res) != 0:
        new_id = res[-1][0]
    else:
        new_id = 0

    filename = str(uuid.uuid4())

    res = cur.execute(f"SELECT video_upload_path FROM posts WHERE video_upload_path='{filename}'")
    res.fetchall()

    if (len(res) != 0):
        print("Error filename already in database")

    extension = str(fileb.filename).split(".")[-1]

    if extension != "mp4":
        print("wrong file type")

    vpath = f'./stored_videos/{filename}.{extension}'

    with open(vpath, 'wb') as video:
        video.write(file)
        video.close()

    
    username = authstring.split("|")

    cur.execute(f"INSERT INTO posts VALUES ({new_id}, {caption}, {vpath}, {username}, {time.time()}, {next_user}, {chain_length-1}, {max_time})'")
    con.commit()

    return RedirectResponse(f'/userhome?auth={authstring}')


@app.post("/continue_post/")
def ContinuePost(file: bytes = File(), fileb: UploadFile = File(), post_id: int = Form(), authstring: str = Form(), next_user: str = Form()):
    res = cur.execute(f"SELECT (video_paths, usernames, next_user, users_remaining) FROM posts WHERE id='{post_id}'")
    res.fetchall()

    (db_video_paths, db_usernames, db_next_user, db_users_remaining) = res

    if db_next_user != authstring.split("|")[0]:
        print("Error wrong user") 
    
    filename = str(uuid.uuid4())

    res = cur.execute(f"SELECT video_upload_path FROM posts WHERE video_upload_path='{filename}'")
    res.fetchall()

    if (len(res) != 0):
        print("Error filename already in database")

    extension = str(fileb.filename).split(".")[-1]

    if extension != "mp4":
        print("wrong file type")

    vpath = f'./stored_videos/{filename}.{extension}'

    with open(vpath, 'wb') as video:
        video.write(file)
        video.close()
    
    video_paths = db_video_paths + "|" + vpath
    usernames = db_usernames + "|" + authstring.split("|")[0]
    users_remaining = db_users_remaining - 1
    
    cur.execute(f"""
        UPDATE posts
        SET video_paths = '{video_paths}',
            usernames = '{usernames}',
            next_user = '{next_user}',
            users_remaining = {users_remaining},
            timestamp = '{str(time.time())}'
        WHERE
            id = {post_id};
    """)
    con.commit()

    return RedirectResponse(f'/userhome?auth={authstring}')

@app.post("/userhome/")
def user_home_page(authstring: str = ""):
    if authstring not in login_hashes:
        return RedirectResponse("/static/login.html")

    return templates.TemplateResponse("user_home.html", {"name": authstring.split("|")[0]})