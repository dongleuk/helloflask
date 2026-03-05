from flask import Flask
import os

app = Flask(__name__)
message = os.getenv("APP_MESSAGE", "Hello from Kubernetes!")

@app.route("/")
def hello():
    return message


@app.route("/goose")
def goose():
    return "It's a goose!"

@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)