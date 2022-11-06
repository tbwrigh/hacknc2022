import sqlite3
import hashlib 
import uuid
import random
import time

from fastapi import FastAPI, Form, File, UploadFile, Request, Response, Header
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse

from typing import Union, Optional

from pathlib import Path

from hashlib import sha256

templates = Jinja2Templates(directory="templates")

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

login_hashes = []

con = sqlite3.connect("user.sqlite", check_same_thread=False)
cur = con.cursor()

@app.on_event("startup")
async def startup():
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT, 
        email TEXT,
        password_hash TEXT,
        firstname TEXT,
        lastname TEXT,
        profile_image_path TEXT DEFAULT 'default.png'
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER,
        caption TEXT,
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


@app.get("/")
async def read_root():
    return RedirectResponse("/static/login.html", status_code=302)

@app.post("/login")
async def login(username: str = Form(), password: str = Form(), timestamp: str = Form()):
    res = cur.execute(f"SELECT password_hash FROM users WHERE username='{username}'")
    res = res.fetchall()

    if (len(res) != 0):
        if res[0][0] == password:
            full_hash = password + '|' + timestamp 
            hashed_string = hashlib.sha256(full_hash.encode('utf-8')).hexdigest()
            hashed_string = username + '|' + hashed_string
            login_hashes.append(hashed_string)

            return RedirectResponse(f"/userhome?auth={hashed_string}", status_code=302)
            # success
        else:
            return RedirectResponse("/static/login.html?error=badpass", status_code=302)
            #bad password
    else:
        return RedirectResponse("/static/login.html?error=badname", status_code=302)
        # bad username
    
@app.post("/new_user") #check if username or email is in system before adding to user
async def new_user(firstname: str= Form(), lastname: str= Form(), username: str = Form(), email: str = Form(), password: str = Form(), timestamp: str = Form()):
    email = email.replace("@", "atsymbol")
    res = cur.execute(f"SELECT email FROM users WHERE email='{email}'")
    res = res.fetchall()

    if (len(res) != 0):
        print("Error email already has account")

    res = cur.execute(f"SELECT username FROM users WHERE username='{username}'")
    res = res.fetchall()

    if (len(res) != 0):
        print("Error email already ascoiated with a account")
    
    cur.execute(f"""
        INSERT INTO users(username, email, password_hash, firstname, lastname) VALUES (?,?,?,?,?)
    """, (username, email, password, firstname, lastname))
    #saves it 
    con.commit()

    full_hash = password + '|' + timestamp 
    hashed_string = hashlib.sha256(full_hash.encode('utf-8')).hexdigest()
    hashed_string = username + '|' + hashed_string
    login_hashes.append(hashed_string)
    
    return RedirectResponse(f"/userhome?auth={hashed_string}", status_code=302)
    #newuser


@app.post("/profile_pic")
async def UploadImage(file: bytes = File(), fileb: UploadFile = File()):
    filename = str(uuid.uuid4())
    
    res = cur.execute(f"SELECT profile_image_path FROM users WHERE profile_image_path='{filename}'")
    res = res.fetchall()

    if (len(res) != 0):
        print("Error filename already in database")

    extension = str(fileb.filename).split(".")[-1]

    if extension != "png" or extension != "jpg":
        print("wrong file type")

    with open(f'./static/images/{filename}.{extension}', 'wb') as image:
        image.write(file)
        image.close()

    return 'got it'

@app.get("/logout")
async def logout(auth: str):
    if auth in login_hashes:
        login_hashes.remove(auth)
    return RedirectResponse("/static/login.html", status_code=302)

@app.post("/new_post")
async def NewPost(post_id: int = Form(), authstring: str = Form(), caption: str = Form(), next_user: str = Form(), chain_length: str = Form(), max_time: int = Form()):
    #take in parameters for files, authstring, and caption
    
    username = authstring.split("|")

    cur.execute(f"INSERT INTO posts VALUES ({new_id}, {caption}, {vpath}, {username}, {time.time()}, {next_user}, {chain_length-1}, {max_time})'")
    con.commit()

    return RedirectResponse(f'/userhome?auth={authstring}', status_code=302)


@app.post("/continue_post")
async def ContinuePost(file: bytes = File(), fileb: UploadFile = File(), post_id: int = Form(), authstring: str = Form(), next_user: str = Form()):
    res = cur.execute(f"SELECT (video_paths, usernames, next_user, users_remaining) FROM posts WHERE id='{post_id}'")
    res = res.fetchall()

    (db_video_paths, db_usernames, db_next_user, db_users_remaining) = res

    if db_next_user != authstring.split("|")[0]:
        print("Error wrong user") 
    
    filename = str(uuid.uuid4())

    res = cur.execute(f"SELECT video_upload_path FROM posts WHERE video_upload_path='{filename}'")
    res = res.fetchall()

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

    return RedirectResponse(f'/userhome?auth={authstring}', status_code=302)

@app.get("/userhome")
async def user_home_page(request: Request, auth: str):
    if auth not in login_hashes:
        return RedirectResponse("/static/login.html", status_code=302)

    return templates.TemplateResponse("user_home.html", {"request": request, "name": auth.split("|")[0], "auth": auth.replace("|", "%7C")})

@app.post("/start-post")
async def start_post(file: UploadFile = File(), auth: str = Form()):
    res = cur.execute(f"SELECT id FROM posts")
    res = res.fetchall()
    if len(res) != 0:
        new_id = res[-1][0]
    else:
        new_id = 0

    filename = str(uuid.uuid4())

    res = cur.execute(f"SELECT video_paths FROM posts WHERE video_paths='{filename}'")
    res = res.fetchall()

    if (len(res) != 0):
        print("Error filename already in database")

    extension = str(file.filename).split(".")[-1]

    if extension != "mp4":
        print("wrong file type")

    vpath = f'./static/stored_videos/{filename}.{extension}'

    with open(vpath, 'wb') as video:
        content = await file.read()
        video.write(content)
        video.close()

    cur.execute(f"INSERT INTO posts(id, video_paths, timestamp) VALUES (?,?,?)", (new_id, f"{filename}.{extension}", time.time()))
    con.commit()

    return RedirectResponse(f'/make-post?auth={auth}&filepath={filename}.{extension}', status_code=302)

@app.get("/make-post")
async def make_post(request: Request, auth: str, filepath: str):
    return templates.TemplateResponse("post.html", {"request": request, "auth": auth, "filepath": filepath})

