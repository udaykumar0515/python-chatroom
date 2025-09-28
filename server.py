"""
Encrypted Terminal Chat Server - Enhanced Version
Usage: python server.py
"""

import socket
import threading
import json
import base64
import struct
import time
import os
from threading import Lock
from datetime import datetime

# Constants
HOST = "0.0.0.0"  # Bind to all interfaces
PORT = 5000
RECV_BUF = 4096
FERNET_KEY = b'ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg='

clients = {}
lock = Lock()

CHAT_HISTORY_FILE = "chat_history.json"

def init_directories():
    pass

def save_message(from_user: str, to_user: str, message: str):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {"timestamp": timestamp, "from": from_user, "to": to_user, "message": message}
        
        # Load existing messages
        messages = []
        if os.path.exists(CHAT_HISTORY_FILE):
            try:
                with open(CHAT_HISTORY_FILE, "r") as f:
                    content = f.read().strip()
                    if content:
                        messages = json.loads(content)
            except:
                messages = []
        
        # Add new message
        messages.append(log_entry)
        
        # Save back to file
        with open(CHAT_HISTORY_FILE, "w") as f:
            json.dump(messages, f, indent=2)
    except:
        pass


def read_exact(sock, n):
    data = b''
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Socket closed")
        data += chunk
    return data

def recv_message(sock):
    meta_len = struct.unpack('!I', read_exact(sock, 4))[0]
    metadata = json.loads(read_exact(sock, meta_len).decode('utf-8'))
    payload = read_exact(sock, metadata['payload_len']) if metadata.get('payload_len', 0) > 0 else None
    return metadata, payload

def send_framed(sock, metadata, payload=None):
    metadata['payload_len'] = len(payload) if payload else 0
    meta_bytes = json.dumps(metadata).encode('utf-8')
    sock.sendall(struct.pack('!I', len(meta_bytes)))
    sock.sendall(meta_bytes)
    if payload:
        sock.sendall(payload)

def broadcast_user_list():
    with lock:
        usernames = list(clients.keys())
    list_response = {"type": "list_response", "users": usernames}
    with lock:
        for client_info in clients.values():
            try:
                send_framed(client_info["conn"], list_response)
            except:
                pass

def broadcast_system_message(message, exclude_user=None):
    system_meta = {"type": "msg", "from": "SYSTEM", "to": "all"}
    system_payload = message.encode('utf-8')
    with lock:
        for username, client_info in clients.items():
            if exclude_user and username == exclude_user:
                continue
            try:
                send_framed(client_info["conn"], system_meta, system_payload)
            except:
                pass

def get_display_name(username):
    with lock:
        return f"[ADMIN] {username}" if username in clients and clients[username]["is_admin"] else username

def handle_client(client_socket, client_addr):
    username = None
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    try:
        metadata, payload = recv_message(client_socket)
        if metadata.get('type') != 'register':
            send_framed(client_socket, {"type": "error", "error": "registration_required"})
            return

        username = metadata.get('from', '').strip()
        if not username:
            send_framed(client_socket, {"type": "error", "error": "invalid_username"})
            return

        with lock:
            if username in clients:
                send_framed(client_socket, {"type": "error", "error": "username_taken"})
                return
            is_admin = len(clients) == 0
            clients[username] = {"conn": client_socket, "addr": f"{client_addr[0]}:{client_addr[1]}", "is_admin": is_admin}

        display_name = get_display_name(username)
        admin_tag = " (ADMIN)" if is_admin else ""
        print(f"[CONNECT] {timestamp} | {username} connected from {client_addr}{admin_tag}")
        send_framed(client_socket, {"type": "register_success", "message": f"Registered as {username}{' with admin privileges' if is_admin else ''}", "is_admin": is_admin})

        broadcast_user_list()
        if not is_admin:
            broadcast_system_message(f"{username} has joined the chat.", exclude_user=username)

        while True:
            metadata, payload = recv_message(client_socket)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            msg_type = metadata.get('type')
            from_user = metadata.get('from')
            display_from = get_display_name(from_user)

            if msg_type == 'msg':
                to_user = metadata.get('to')
                print(f"[META] {timestamp} | type=msg | from={display_from} | to={to_user}")
                
                if payload:
                    # Show encrypted payload for educational purposes
                    payload_b64 = base64.b64encode(payload).decode('ascii')
                    print(f"[ENCRYPTED_PAYLOAD_BASE64] {payload_b64}")
                    
                    # Show readable log format
                    if to_user == 'all':
                        print(f"[LOG] {display_from} → ALL: {payload_b64[:50]}{'...' if len(payload_b64) > 50 else ''}")
                    else:
                        target_display = get_display_name(to_user) if to_user in clients else to_user
                        print(f"[LOG] {display_from} → {target_display}: {payload_b64[:50]}{'...' if len(payload_b64) > 50 else ''}")
                    
                    try:
                        from cryptography.fernet import Fernet
                        fernet = Fernet(FERNET_KEY)
                        decrypted_msg = fernet.decrypt(payload).decode('utf-8')
                        save_message(from_user, to_user, decrypted_msg)
                    except:
                        pass

                with lock:
                    if to_user == 'all':
                        for target_user, client_info in clients.items():
                            if target_user != from_user:
                                try:
                                    send_framed(client_info["conn"], metadata, payload)
                                except:
                                    pass
                    else:
                        if to_user in clients:
                            try:
                                send_framed(clients[to_user]["conn"], metadata, payload)
                            except:
                                pass
                        else:
                            send_framed(client_socket, {"type": "error", "error": "recipient_not_found"})

            elif msg_type == 'file_start':
                to_user = metadata.get('to')
                filename = metadata.get('filename', 'unknown')
                filesize = metadata.get('filesize', 0)
                print(f"[META] {timestamp} | type=file_start | from={display_from} | to={to_user} | filename={filename} | filesize={filesize}")
                
                with lock:
                    if to_user in clients:
                        try:
                            send_framed(clients[to_user]["conn"], metadata, payload)
                        except:
                            pass
                    else:
                        send_framed(client_socket, {"type": "error", "error": "recipient_not_found"})

            elif msg_type == 'file_chunk':
                to_user = metadata.get('to')
                seq = metadata.get('seq', 0)
                last = metadata.get('last', False)
                print(f"[META] {timestamp} | type=file_chunk | from={display_from} | to={to_user} | seq={seq} | last={last}")
                if payload:
                    payload_b64 = base64.b64encode(payload).decode('ascii')
                    print(f"[ENCRYPTED_PAYLOAD_BASE64] {payload_b64}")
                with lock:
                    if to_user in clients:
                        try:
                            send_framed(clients[to_user]['conn'], metadata, payload)
                        except:
                            pass

            elif msg_type == 'list_request':
                print(f"[META] {timestamp} | type=list_request | from={display_from}")
                with lock:
                    usernames = list(clients.keys())
                send_framed(client_socket, {"type": "list_response", "users": usernames})

            elif msg_type == 'admin_history':
                print(f"[META] {timestamp} | type=admin_history | from={display_from}")
                with lock:
                    if username in clients and clients[username]["is_admin"]:
                        try:
                            if os.path.exists(CHAT_HISTORY_FILE):
                                with open(CHAT_HISTORY_FILE, "r") as f:
                                    messages = json.load(f)
                                    recent_messages = messages[-50:] if len(messages) > 50 else messages
                                send_framed(client_socket, {
                                    "type": "admin_history_response",
                                    "messages": recent_messages
                                })
                            else:
                                send_framed(client_socket, {"type": "admin_history_response", "messages": []})
                        except:
                            send_framed(client_socket, {"type": "error", "error": "Failed to load history"})
                    else:
                        send_framed(client_socket, {"type": "error", "error": "admin_privileges_required"})

            else:
                print(f"[META] {timestamp} | type=unknown | from={display_from}")

    except Exception as e:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        display_name = get_display_name(username) if username else 'unknown'
        print(f"[DISCONNECT] {timestamp} | {display_name} disconnected: {e}")

    finally:
        if username:
            display_name = get_display_name(username)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[INFO] {timestamp} | {display_name} disconnected")
            with lock:
                clients.pop(username, None)
            broadcast_system_message(f"{username} has left the chat.")
            broadcast_user_list()
        try:
            client_socket.close()
        except:
            pass

def main():
    init_directories()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(10)
        print(f"Server listening on {HOST}:{PORT}")
        print("Waiting for connections...")
        print("First client will become ADMIN")
        print("Chat history and admin monitoring enabled")
        print("=" * 50)

        while True:
            client_socket, client_addr = server_socket.accept()
            threading.Thread(target=handle_client, args=(client_socket, client_addr), daemon=True).start()

    except KeyboardInterrupt:
        print("\nServer shutting down...")
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        server_socket.close()

if __name__ == "__main__":
    main()
