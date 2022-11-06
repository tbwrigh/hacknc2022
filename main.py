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

import os

import ffmpeg

templates = Jinja2Templates(directory="templates")

templates.env.filters["zip"] = zip

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
        users_remaining INT,
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
async def NewPost(post_id: int = Form(), auth: str = Form(), caption: str = Form(), next_user: str = Form(), chain_length: int = Form(), max_time: int = Form()):
    username = auth.split("|")[0]

    cur.execute(f"""
    UPDATE posts
    SET caption = ?,
        usernames = ?,
        next_user = ?,
        users_remaining = ?,
        time_limit = ?
    WHERE id = ?
    """, (caption, username, next_user, chain_length-1, max_time, post_id))
    con.commit()

    return RedirectResponse(f'/userhome?auth={auth}', status_code=302)


@app.post("/continue-post")
async def ContinuePost(file: UploadFile = File(), post_id: int = Form(), auth: str = Form()):
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

    os.rename(f"./static/working_videos/{post_id}.mp4", f"./static/working_videos/{post_id}_old.mp4")

    old_file = ffmpeg.input(f"./static/working_videos/{post_id}_old.mp4")
    new_file = ffmpeg.input(vpath)

    ffmpeg.concat(old_file, new_file).output(f"./static/working_videos/{post_id}.mp4").run()

    res = cur.execute(f"SELECT video_paths FROM posts WHERE id={post_id}")
    new_video_paths = res.fetchall()[0][0] + "|" + f"{filename}.{extension}"

    cur.execute(f"UPDATE posts SET video_paths=? WHERE id=?", (new_video_paths, post_id))
    con.commit()

    return RedirectResponse(f'/continue?auth={auth}&id={post_id}', status_code=302)

@app.post("/add-to-post")
def add_to_post(auth: str = Form(), post_id: str = Form(), next_user: str = Form()):
    res = cur.execute(f"SELECT users_remaining, usernames FROM posts WHERE id={post_id}")
    res = res.fetchall()
    new_chain_length = res[0][0] - 1
    new_usernames = res[0][1] + "|" + auth.split("|")[0]

    cur.execute(f"""
    UPDATE posts
    SET usernames=?,
        next_user=?,
        users_remaining=?
    WHERE id=?
    """, (new_usernames, next_user, new_chain_length, post_id))
    con.commit()

    return RedirectResponse(f"/userhome?auth={auth}", status_code=302)

@app.get("/continue")
def continue_continue(request: Request, auth: str, id: str):
    return templates.TemplateResponse("continue.html", {"request": request, "auth": auth, "post_id": id})

@app.get("/userhome")
async def user_home_page(request: Request, auth: str):
    if auth not in login_hashes:
        return RedirectResponse("/static/login.html", status_code=302)

    res = cur.execute("SELECT id, usernames, caption FROM posts")
    res = res.fetchall()

    res = list(res)

    for i in range(len(res)):
        res[i] = list(res[i])
        res[i][1] = res[i][1].split("|")

    print(res)

    return templates.TemplateResponse("user_home.html", {"request": request, "name": auth.split("|")[0], "auth": auth.replace("|", "%7C"), "res": res})

@app.post("/start-post")
async def start_post(file: UploadFile = File(), auth: str = Form()):
    res = cur.execute(f"SELECT id FROM posts")
    res = res.fetchall()
    if len(res) != 0:
        new_id = res[-1][0] + 1
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

    ffmpeg.input(vpath).output(f"./static/working_videos/{new_id}.mp4").run()

    cur.execute(f"INSERT INTO posts(id, video_paths, timestamp) VALUES (?,?,?)", (new_id, f"{filename}.{extension}", time.time()))
    con.commit()

    return RedirectResponse(f'/make-post?auth={auth}&id={new_id}&filepath={filename}.{extension}', status_code=302)

@app.get("/make-post")
async def make_post(request: Request, auth: str, id: int, filepath: str):
    return templates.TemplateResponse("post.html", {"request": request, "auth": auth, "post_id": id})

@app.get("/inbox")
async def inbox(request: Request, auth: str):
    name = auth.split('|')[0]

    res = cur.execute(f"SELECT id, usernames FROM posts WHERE next_user='{name}'")
    res = res.fetchall()

    for i in range(len(res)):
        res[i] = list(res[i])
        res[i].append(res[i][1].split("|")[0])
        res[i].append(res[i][1].split("|")[-1])

    return templates.TemplateResponse("inbox.html", {"request": request, "auth": auth, "res": res})

@app.get("/upnext")
def upnext(request: Request, auth: str, id: str):

    return templates.TemplateResponse("upnext.html", {"request": request, "auth": auth, "post_id": id})