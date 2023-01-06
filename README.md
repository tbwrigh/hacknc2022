# The Story Goes


## Originally Built for HackNC 2022
### Original Contributors: Tyler Wright, Megan Kulshekar, Katie Duncan

### Now Maintained By: Tyler Wright & Megan Kulshekar 


### Overview
The Story Goes is a new take on social media. We believe social media is for story telling. So we reimagined traditional social media to be like our favorite childhood games. We thought about telephone and one word story. Games where each person contributed just a fragment of speech to the greater conversation. Using that for inspiration, The Story Goes was born. THe Story Goes starts with one person and a short video. They send an invite to another person to add another short video. THe combined video grows with time. 

### Technology
The Story Goes is primarily written in Python with the FastAPI library and Jinja2 templating engine. It uses SQLite as a simple database. There are a handful of other smaller libraries at play, but each of them serve just a small purpose in the greater context of our application.

### Running It
Start off by pulling this repository. Install all the dependencies for python. THen just run: `uvicorn main:app --host 0.0.0.0 --port 8000`.
