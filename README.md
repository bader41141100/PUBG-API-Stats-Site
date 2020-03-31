# NodeJS, Django (python) and MySQL based PUBG Stats Site

- Uses Django as the backend, to communicate to MySQL using the amazing Django ORM.
- NodeJS handles rendering templates using nunjucks.
- NodeJS simply passes requests from the front-end to the backend.
- Python does all the heavy lifting.

# Getting started
- Any version of Python3 should work.
- Install the python dependencies using `pip install -r requirements.txt`.
- Install node dependencies using `npm install`.
- Setup MySQL and change the settings within `statsapp/settings.py` to reflect your local database.
- Change `API_TOKEN` within `api/settings.py` to your PUBG API Token.
- Run the initial migrations for Django `python manange.py migrate`, so it generates the neccessary schema and tables.
- Start django first using `python python server.py`
- Change `threads=8` in `server.py` to the amount of cores your machine has.
- Start node using `node server` or `nodemon server` if you have nodemon installed.
- Navigate to localhost, and search away.