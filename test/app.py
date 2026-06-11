"""Minimal Flask application used for local IPv4/IPv6 experiments.

用于本地 IPv4/IPv6 实验的最小 Flask 应用。
"""

from flask import Flask, request
import socket

app = Flask(__name__)

@app.route("/")
def index():
    """Return basic client and host information for connectivity checks.

    返回基础客户端和主机信息，用于连接测试。
    """

    return {
        "message": "hello ipv6",
        "client_ip": request.remote_addr,
        "hostname": socket.gethostname()
    }

if __name__ == "__main__":
    # Listen on all IPv4 interfaces; use "::" when specifically testing IPv6.
    # 监听所有 IPv4 网卡；专门测试 IPv6 时可改用 "::"。
    app.run(
        # Alternative host value for IPv6 experiments.
        # IPv6 实验时可使用的备用主机地址。
        # host="::",
        host="0.0.0.0",
        port=30000,
        debug=True
    )
