from flask import Flask, request
import socket

app = Flask(__name__)

@app.route("/")
def index():
    return {
        "message": "hello ipv6",
        "client_ip": request.remote_addr,
        "hostname": socket.gethostname()
    }

if __name__ == "__main__":
    # 监听所有 IPv4/IPv6
    app.run(
        host="::",
        port=9000,
        debug=True
    )