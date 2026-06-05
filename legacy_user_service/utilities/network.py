"""
网络工具模块
用于获取和显示本地及公网 IPv6/IPv4 地址信息
"""
import socket
import requests
from typing import List, Optional

import socket
import logging

logger = logging.getLogger("uvicorn.error")








def get_local_ipv6_addresses() -> List[str]:
    """获取本机所有 IPv6 地址"""
    ipv6_addresses = []

    try:
        # 获取主机名
        hostname = socket.gethostname()

        # 获取所有地址信息
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_INET6)

        for info in addr_info:
            ip = info[4][0]
            # 移除 scope id (例如 fe80::1%eth0 -> fe80::1)
            ip = ip.split('%')[0]
            if ip not in ipv6_addresses:
                ipv6_addresses.append(ip)

        # 也可以通过 socket 连接方式获取
        try:
            s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            s.connect(("2001:4860:4860::8888", 80))  # Google DNS IPv6
            local_ip = s.getsockname()[0]
            if local_ip not in ipv6_addresses:
                ipv6_addresses.append(local_ip)
            s.close()
        except:
            pass

    except Exception as e:
        print(f"获取本地 IPv6 地址时出错: {e}")

    return ipv6_addresses


def get_public_ipv6(timeout: int = 3) -> str:
    """
    获取公网 IPv6 地址

    Args:
        timeout: 请求超时时间（秒）

    Returns:
        公网 IPv6 地址字符串，如果获取失败则返回错误信息
    """
    try:
        # 尝试多个 IPv6 检测服务
        services = [
            "https://api64.ipify.org?format=text",
            "https://v6.ident.me/",
            "https://ipv6.icanhazip.com/",
        ]

        for service in services:
            try:
                response = requests.get(service, timeout=timeout)
                if response.status_code == 200:
                    ip = response.text.strip()
                    # 验证是否为 IPv6
                    if ':' in ip:
                        return ip
            except:
                continue

        return "无法获取公网 IPv6"
    except Exception as e:
        return f"获取失败: {e}"


def get_local_ipv4() -> Optional[str]:
    """获取本地 IPv4 地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ipv4 = s.getsockname()[0]
        s.close()
        return local_ipv4
    except:
        return "127.0.0.1"


def classify_ipv6_address(ip: str) -> str:
    """
    分类 IPv6 地址类型

    Args:
        ip: IPv6 地址字符串

    Returns:
        地址类型描述
    """
    if ip == "::1":
        return "回环地址 (Loopback)"
    elif ip.startswith("fe80:"):
        return "链路本地地址 (Link-Local)"
    elif ip.startswith("fd") or ip.startswith("fc"):
        return "唯一本地地址 (ULA)"
    elif ip.startswith("::ffff:"):
        return "IPv4 映射地址"
    else:
        return "全局单播地址 (Global)"


def print_network_info(port: int, show_ipv4: bool = True):
    """
    打印网络地址信息

    Args:
        port: 服务监听的端口号
        show_ipv4: 是否显示 IPv4 地址信息
    """
    print("\n" + "=" * 60)
    print("🌐 网络地址信息")
    print("=" * 60)

    # 本地 IPv6 地址
    local_ipv6s = get_local_ipv6_addresses()
    if local_ipv6s:
        print("\n📍 本地 IPv6 地址:")
        for idx, ip in enumerate(local_ipv6s, 1):
            ip_type = classify_ipv6_address(ip)
            print(f"   {idx}. [{ip}]:{port} - {ip_type}")
            print(f"      → http://[{ip}]:{port}")
            print(f"      → http://[{ip}]:{port}/docs (API文档)")
    else:
        print("\n⚠️  未检测到本地 IPv6 地址")

    # 公网 IPv6 地址
    print("\n🌍 公网 IPv6 地址:")
    public_ipv6 = get_public_ipv6()
    if public_ipv6 and "无法" not in public_ipv6 and "失败" not in public_ipv6:
        print(f"   [{public_ipv6}]:{port}")
        print(f"   → http://[{public_ipv6}]:{port}")
        print(f"   → http://[{public_ipv6}]:{port}/docs (API文档)")
    else:
        print(f"   {public_ipv6}")
        print("   💡 提示: 如果没有公网 IPv6，这是正常的")

    # IPv4 地址（可选）
    if show_ipv4:
        print("\n📌 IPv4 地址:")
        local_ipv4 = get_local_ipv4()
        print(f"   {local_ipv4}:{port}")
        print(f"   → http://{local_ipv4}:{port}")
        print(f"   → http://{local_ipv4}:{port}/docs (API文档)")

    print("\n" + "=" * 60)
    print("✅ 服务器启动成功!")
    print("=" * 60 + "\n")


def get_network_summary(port: int) -> dict:
    """
    获取网络信息摘要（用于程序化处理）

    Args:
        port: 服务监听的端口号

    Returns:
        包含网络信息的字典
    """
    return {
        "port": port,
        "local_ipv6": get_local_ipv6_addresses(),
        "public_ipv6": get_public_ipv6(),
        "local_ipv4": get_local_ipv4(),
    }





def log_network_info(port: int):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ipv4 = s.getsockname()[0]
        s.close()
    except Exception:
        ipv4 = "unavailable"

    try:
        ipv6_list = [
            info[4][0]
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET6)
            if not info[4][0].startswith("fe80") and info[4][0] != "::1"
        ]
        ipv6 = ipv6_list[0] if ipv6_list else "unavailable"
    except Exception:
        ipv6 = "unavailable"

    logger.info(f"Public IPv4: http://{ipv4}:{port}")
    logger.info(f"Public IPv6: http://[{ipv6}]:{port}")

