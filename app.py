from flask import Flask
import socket

app = Flask(__name__)

@app.route("/")
def home():
    return f"Hello from Sahil the CI/CD pipeline creator! Served by host: {socket.gethostname()}\n"

@app.route("/health")
def health():
    return "OK", 200