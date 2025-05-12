#!/usr/bin/env python3
"""
MCP天气查询示例
使用OpenWeatherMap API和DeepSeek大模型实现天气查询
"""

import os
import sys
import argparse
import threading
import subprocess
import time
import socket

# 默认MCP服务器端口
DEFAULT_PORT = 8765

def is_port_available(port):
    """检查指定端口是否可用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("localhost", port))
            return True
        except socket.error:
            return False

def find_available_port(start_port=8700, max_attempts=100):
    """寻找可用端口"""
    for port in range(start_port, start_port + max_attempts):
        if is_port_available(port):
            return port
    raise RuntimeError(f"无法找到可用端口 ({start_port} - {start_port + max_attempts - 1})")

def start_server(port):
    """启动MCP服务器"""
    print(f"启动MCP服务器 (端口: {port})...")
    subprocess.run(["python", "server.py", "--port", str(port)])

def start_client(port):
    """启动MCP客户端"""
    print(f"启动MCP客户端 (连接端口: {port})...")
    subprocess.run(["python", "client.py", "--port", str(port)])

def check_api_keys():
    """检查API密钥是否已设置"""
    from dotenv import load_dotenv
    load_dotenv()
    
    openweather_key = os.getenv("OPENWEATHERMAP_API_KEY")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    
    if not openweather_key or openweather_key == "your_api_key_here":
        print("错误: 请在.env文件中设置OPENWEATHERMAP_API_KEY")
        return False
    
    if not deepseek_key or deepseek_key == "your_api_key_here":
        print("错误: 请在.env文件中设置DEEPSEEK_API_KEY")
        return False
    
    return True

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="MCP天气查询示例")
    parser.add_argument("--server", action="store_true", help="仅启动服务器")
    parser.add_argument("--client", action="store_true", help="仅启动客户端")
    parser.add_argument("--port", type=int, default=None, help=f"指定端口号，默认自动选择可用端口")
    args = parser.parse_args()
    
    # 检查API密钥
    if not check_api_keys():
        sys.exit(1)
    
    # 确定端口号
    if args.port is not None:
        port = args.port
        if not is_port_available(port):
            print(f"警告: 端口 {port} 已被占用，尝试自动选择可用端口...")
            port = find_available_port()
    else:
        # 如果没有指定端口，尝试使用默认端口或自动选择
        if is_port_available(DEFAULT_PORT):
            port = DEFAULT_PORT
        else:
            print(f"默认端口 {DEFAULT_PORT} 已被占用，自动选择可用端口...")
            port = find_available_port()
    
    print(f"使用端口 {port} 进行MCP通信")
    
    if args.server:
        start_server(port)
    elif args.client:
        start_client(port)
    else:
        # 同时启动服务器和客户端
        server_thread = threading.Thread(target=start_server, args=(port,))
        server_thread.daemon = True
        server_thread.start()
        
        # 等待服务器启动
        print("等待服务器启动...")
        time.sleep(2)
        
        # 启动客户端
        start_client(port)

if __name__ == "__main__":
    main()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
