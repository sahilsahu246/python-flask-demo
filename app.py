from flask import Flask
import socket

app = Flask(__name__)

@app.route("/")
def home():
    return f"Hello from the CI/CD pipeline! Served by host: {socket.gethostname()}\n"

@app.route("/health")
def health():
    return "OK", 200