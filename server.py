#!/usr/bin/env python3
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
import typing
import os
import sys
from threading import Lock

# Constants
HOST = "0.0.0.0"  # Bind to all interfaces
PORT = 5000
RECV_BUF = 4096
FERNET_KEY = b'ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg='

# Global state - Enhanced to store client objects with admin info
clients: typing.Dict[str, dict] = {}  # username -> {"conn": socket, "addr": addr, "is_admin": bool}
lock = Lock()

def read_exact(sock: socket.socket, n: int) -> bytes:
    """Read exactly n bytes from socket or raise on disconnect."""
    data = b''
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Socket closed during read")
        data += chunk
    return data

def recv_message(sock: socket.socket) -> typing.Tuple[dict, typing.Optional[bytes]]:
    """Receive framed message: metadata + optional payload."""
    # Read metadata length
    meta_len_bytes = read_exact(sock, 4)
    meta_len = struct.unpack('!I', meta_len_bytes)[0]

    # Read metadata JSON
    meta_bytes = read_exact(sock, meta_len)
    metadata = json.loads(meta_bytes.decode('utf-8'))

    # Read payload if specified
    payload = None
    if 'payload_len' in metadata and metadata['payload_len'] > 0:
        payload = read_exact(sock, metadata['payload_len'])

    return metadata, payload

def send_framed(sock: socket.socket, metadata: dict, payload: typing.Optional[bytes] = None):
    """Send framed message: metadata + optional payload."""
    # Set payload length in metadata
    if payload:
        metadata['payload_len'] = len(payload)
    else:
        metadata['payload_len'] = 0

    # Serialize metadata
    meta_json = json.dumps(metadata)
    meta_bytes = meta_json.encode('utf-8')

    # Send metadata length and metadata
    sock.sendall(struct.pack('!I', len(meta_bytes)))
    sock.sendall(meta_bytes)

    # Send payload if present
    if payload:
        sock.sendall(payload)

def broadcast_user_list():
    """Send updated user list to all connected clients."""
    with lock:
        usernames = list(clients.keys())

    list_response = {
        "type": "list_response",
        "users": usernames
    }

    with lock:
        for username, client_info in clients.items():
            try:
                send_framed(client_info["conn"], list_response)
            except:
                pass  # Client may be disconnecting

def broadcast_system_message(message: str, exclude_user: str = None):
    """Broadcast a system message to all connected clients."""
    system_meta = {
        "type": "msg",
        "from": "SYSTEM",
        "to": "all"
    }

    # Create fake encrypted payload for system messages (they're not actually encrypted)
    system_payload = message.encode('utf-8')

    with lock:
        for username, client_info in clients.items():
            if exclude_user and username == exclude_user:
                continue
            try:
                send_framed(client_info["conn"], system_meta, system_payload)
            except:
                pass

def get_display_name(username: str) -> str:
    """Get display name with admin tag if applicable."""
    with lock:
        if username in clients and clients[username]["is_admin"]:
            return f"[ADMIN] {username}"
        return username

def handle_client(client_socket: socket.socket, client_addr: tuple):
    """Handle individual client connection."""
    username = None
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    try:
        # First message should be registration
        metadata, payload = recv_message(client_socket)

        if metadata.get('type') != 'register':
            send_framed(client_socket, {
                "type": "error", 
                "error": "registration_required"
            })
            return

        username = metadata.get('from', '').strip()
        if not username:
            send_framed(client_socket, {
                "type": "error", 
                "error": "invalid_username"
            })
            return

        # Check for duplicate username and assign admin status
        with lock:
            if username in clients:
                send_framed(client_socket, {
                    "type": "error", 
                    "error": "username_taken"
                })
                return

            # First client becomes admin
            is_admin = len(clients) == 0
            clients[username] = {
                "conn": client_socket,
                "addr": f"{client_addr[0]}:{client_addr[1]}",
                "is_admin": is_admin
            }

        display_name = get_display_name(username)
        admin_tag = " (ADMIN)" if is_admin else ""
        print(f"[CONNECT] {timestamp} | {username} connected from {client_addr}{admin_tag}")

        # Send success response
        send_framed(client_socket, {
            "type": "register_success",
            "message": f"Registered as {username}{' with admin privileges' if is_admin else ''}"
        })

        # Broadcast updated user list
        broadcast_user_list()

        # Announce new user to others
        if not is_admin:  # Don't announce admin joining
            broadcast_system_message(f"{username} has joined the chat.", exclude_user=username)

        # Main message handling loop
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
                    # Enhanced encrypted message logging
                    payload_b64 = base64.b64encode(payload).decode('ascii')
                    print(f"[ENCRYPTED_PAYLOAD_BASE64] {payload_b64}")

                    # New: Show encrypted message log in readable format
                    if to_user == 'all':
                        print(f"[LOG] {display_from} → ALL: {payload_b64[:50]}{'...' if len(payload_b64) > 50 else ''}")
                    else:
                        target_display = get_display_name(to_user) if to_user in clients else to_user
                        print(f"[LOG] {display_from} → {target_display}: {payload_b64[:50]}{'...' if len(payload_b64) > 50 else ''}")

                # Forward message
                with lock:
                    if to_user == 'all':
                        # Broadcast to all clients except sender
                        for target_user, client_info in clients.items():
                            if target_user != from_user:
                                try:
                                    send_framed(client_info["conn"], metadata, payload)
                                except:
                                    pass
                    else:
                        # Private message
                        if to_user in clients:
                            try:
                                send_framed(clients[to_user]["conn"], metadata, payload)
                            except:
                                pass
                        else:
                            # Recipient not found
                            send_framed(client_socket, {
                                "type": "error",
                                "error": "recipient_not_found"
                            })

            elif msg_type == 'file_start':
                to_user = metadata.get('to')
                filename = metadata.get('filename', 'unknown')
                filesize = metadata.get('filesize', 0)
                print(f"[META] {timestamp} | type=file_start | from={display_from} | to={to_user} | filename={filename} | filesize={filesize}")

                # Forward file_start to recipient
                with lock:
                    if to_user in clients:
                        try:
                            send_framed(clients[to_user]["conn"], metadata, payload)
                        except:
                            pass
                    else:
                        send_framed(client_socket, {
                            "type": "error",
                            "error": "recipient_not_found"
                        })

            elif msg_type == 'file_chunk':
                to_user = metadata.get('to')
                seq = metadata.get('seq', 0)
                last = metadata.get('last', False)
                print(f"[META] {timestamp} | type=file_chunk | from={display_from} | to={to_user} | seq={seq} | last={last}")
                if payload:
                    payload_b64 = base64.b64encode(payload).decode('ascii')
                    print(f"[ENCRYPTED_PAYLOAD_BASE64] {payload_b64}")

                # Forward chunk to recipient
                with lock:
                    if to_user in clients:
                        try:
                            send_framed(clients[to_user]["conn"], metadata, payload)
                        except:
                            pass

            elif msg_type == 'list_request':
                print(f"[META] {timestamp} | type=list_request | from={display_from}")
                with lock:
                    usernames = list(clients.keys())
                send_framed(client_socket, {
                    "type": "list_response",
                    "users": usernames
                })

            else:
                print(f"[META] {timestamp} | type=unknown | from={display_from}")

    except Exception as e:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        display_name = get_display_name(username) if username else 'unknown'
        print(f"[DISCONNECT] {timestamp} | {display_name} disconnected: {e}")

    finally:
        # Enhanced graceful disconnect handling
        if username:
            display_name = get_display_name(username)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[INFO] {display_name} disconnected")

            with lock:
                clients.pop(username, None)

            # Broadcast disconnect message to remaining clients
            broadcast_system_message(f"{username} has left the chat.")
            broadcast_user_list()

        try:
            client_socket.close()
        except:
            pass

def main():
    """Main server function."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(10)
        print(f"Server listening on {HOST}:{PORT}")
        print("Waiting for connections...")
        print("First client will become ADMIN")
        print("=" * 50)

        while True:
            client_socket, client_addr = server_socket.accept()
            client_thread = threading.Thread(
                target=handle_client, 
                args=(client_socket, client_addr),
                daemon=True
            )
            client_thread.start()

    except KeyboardInterrupt:
        print("\nServer shutting down...")
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        server_socket.close()

if __name__ == "__main__":
    main()
