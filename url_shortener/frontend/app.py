from flask import Flask, send_from_directory
import os

app = Flask(__name__, static_folder='.')

@app.route('/')
@app.route('/<path:path>')
def serve_file(path='index.html'):
    return send_from_directory('.', path)

if __name__ == '__main__':
    print("Serving at http://localhost:5500")
    app.run(port=5500, debug=True)