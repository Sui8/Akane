# Replitなどでホストする時にサーバーを立てるプログラム
from flask import Flask
from threading import Thread


app = Flask("")


@app.route("/")
def main():
    return "Akane Status: Online"


def run():
    app.run("0.0.0.0", port=8080)


def keep_alive():
    srv = Thread(target=run)
    srv.start()
