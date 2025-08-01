from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit
import subprocess
import threading
import os
import pty
import select

app = Flask(__name__)
socketio = SocketIO(app)

login_output = ""
login_process = None

@app.route("/")
def index():
    return render_template("index.html", login_output=login_output)

@app.route("/start-login", methods=["GET"])
def start_login():
    global login_output, login_process

    cmd = ["gcloud", "auth", "login", "--no-launch-browser"]
    login_process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    login_output = ""

    def read_output():
        global login_output
        for line in login_process.stdout:
            login_output += line

    threading.Thread(target=read_output, daemon=True).start()

    return redirect(url_for("index"))

@app.route("/submit-auth-code", methods=["POST"])
def submit_auth_code():
    global login_process
    code = request.form.get("auth_code")

    if login_process and login_process.stdin:
        try:
            login_process.stdin.write(code + "\n")
            login_process.stdin.flush()
        except Exception as e:
            return f"<pre>❌ Failed to submit code: {e}</pre>"

    return redirect(url_for("index"))

@app.route("/run-fetch")
def run_fetch():
    subprocess.run(["python", "fetch_env_data.py"])
    return redirect(url_for("show_report"))

@app.route("/report")
def show_report():
    return render_template("report.html")

@app.route("/terminal")
def terminal():
    return render_template("terminal.html")

@socketio.on('start_terminal')
def start_terminal():
    pid, fd = pty.fork()
    if pid == 0:
        subprocess.run(["bash"])
    else:
        socketio.start_background_task(read_and_emit_output, fd)

        @socketio.on('input')
        def handle_input(data):
            os.write(fd, data['input'].encode())

def read_and_emit_output(fd):
    while True:
        if select.select([fd], [], [], 0.1)[0]:
            output = os.read(fd, 1024).decode(errors='ignore')
            socketio.emit('output', {'output': output})

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=7432, debug=True)
