#!/usr/bin/env python3
"""
Encrypted Terminal Chat Client - Enhanced Version
Usage: python client.py
"""

import socket
import threading
import json
import struct
import os
import sys
import base64
from cryptography.fernet import Fernet

# Constants
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5000
FERNET_KEY = b'ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg='
CHUNK_SIZE = 4096

def read_exact(sock: socket.socket, n: int) -> bytes:
    """Read exactly n bytes from socket or raise on disconnect."""
    data = b''
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Socket closed during read")
        data += chunk
    return data

def recv_message(sock: socket.socket):
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

def send_framed(sock: socket.socket, metadata: dict, payload: bytes = None):
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

def register_with_server(sock: socket.socket, username: str):
    """Register username with server."""
    register_meta = {
        "type": "register",
        "from": username
    }
    send_framed(sock, register_meta)

    # Wait for response
    response_meta, _ = recv_message(sock)

    if response_meta.get('type') == 'error':
        error = response_meta.get('error', 'unknown_error')
        if error == 'username_taken':
            print("Error: Username is already taken. Please choose a different name.")
        elif error == 'invalid_username':
            print("Error: Invalid username provided.")
        else:
            print(f"Error: {error}")
        return False
    elif response_meta.get('type') == 'register_success':
        message = response_meta.get('message', f'Registered as {username}')
        print(message)
        if 'admin privileges' in message:
            print("🔑 You are now the chat administrator!")
        return True
    else:
        print("Unexpected server response during registration")
        return False

def send_loop(sock: socket.socket, username: str, fernet: Fernet):
    """Main send loop - handles user input and commands."""
    print("Type /help for commands")

    while True:
        try:
            user_input = input().strip()

            if not user_input:
                continue

            if user_input == '/quit':
                print("Disconnecting...")
                sock.close()
                os._exit(0)

            elif user_input == '/help':
                print("Available commands:")
                print("  /all <message>         - Broadcast message to all users")
                print("  /msg <user> <message>  - Send private message to specific user")
                print("  /file <user> <path>    - Send file to specific user")
                print("  /list                  - Show list of active users")
                print("  /quit                  - Disconnect and exit")
                print("  /help                  - Show this help message")

            elif user_input == '/list':
                list_meta = {
                    "type": "list_request",
                    "from": username
                }
                send_framed(sock, list_meta)

            elif user_input.startswith('/all '):
                message = user_input[5:]  # Remove '/all '
                if message:
                    encrypted_payload = fernet.encrypt(message.encode('utf-8'))
                    msg_meta = {
                        "type": "msg",
                        "from": username,
                        "to": "all"
                    }
                    send_framed(sock, msg_meta, encrypted_payload)
                else:
                    print("Usage: /all <message>")

            elif user_input.startswith('/msg '):
                parts = user_input[5:].split(' ', 1)  # Remove '/msg ' and split once
                if len(parts) >= 2:
                    target_user, message = parts
                    encrypted_payload = fernet.encrypt(message.encode('utf-8'))
                    msg_meta = {
                        "type": "msg",
                        "from": username,
                        "to": target_user
                    }
                    send_framed(sock, msg_meta, encrypted_payload)
                else:
                    print("Usage: /msg <user> <message>")

            elif user_input.startswith('/file '):
                parts = user_input[6:].split(' ', 1)  # Remove '/file ' and split once
                if len(parts) >= 2:
                    target_user, filepath = parts

                    if not os.path.exists(filepath):
                        print(f"Error: File '{filepath}' not found")
                        continue

                    try:
                        filename = os.path.basename(filepath)
                        filesize = os.path.getsize(filepath)

                        # Send file_start metadata
                        file_start_meta = {
                            "type": "file_start",
                            "from": username,
                            "to": target_user,
                            "filename": filename,
                            "filesize": filesize
                        }
                        send_framed(sock, file_start_meta)

                        # Send file in chunks
                        with open(filepath, 'rb') as file:
                            seq = 1
                            while True:
                                chunk = file.read(CHUNK_SIZE)
                                if not chunk:
                                    break

                                encrypted_chunk = fernet.encrypt(chunk)
                                is_last = len(chunk) < CHUNK_SIZE

                                chunk_meta = {
                                    "type": "file_chunk",
                                    "from": username,
                                    "to": target_user,
                                    "filename": filename,  # Add filename for tracking
                                    "seq": seq,
                                    "last": is_last
                                }
                                send_framed(sock, chunk_meta, encrypted_chunk)

                                seq += 1
                                if is_last:
                                    break

                        print(f"File '{filename}' sent to {target_user}")

                    except Exception as e:
                        print(f"Error sending file: {e}")
                else:
                    print("Usage: /file <user> <filepath>")

            else:
                print("Unknown command. Type /help for available commands.")

        except EOFError:
            print("\nDisconnecting...")
            sock.close()
            os._exit(0)
        except Exception as e:
            print(f"Send error: {e}")
            break

def recv_loop(sock: socket.socket, username: str, fernet: Fernet):
    """Receive loop - handles incoming messages."""
    # Ensure downloads directory exists
    os.makedirs('downloads', exist_ok=True)

    # Track ongoing file transfers - Enhanced for corruption checking
    file_transfers = {}  # (from_user, filename) -> file_info

    while True:
        try:
            metadata, payload = recv_message(sock)
            msg_type = metadata.get('type')

            if msg_type == 'msg':
                from_user = metadata.get('from')
                to_user = metadata.get('to')

                if payload:
                    try:
                        # Handle system messages (not encrypted)
                        if from_user == 'SYSTEM':
                            system_msg = payload.decode('utf-8')
                            print(f"🔔 {system_msg}")
                        else:
                            # Regular encrypted message
                            decrypted_msg = fernet.decrypt(payload).decode('utf-8')
                            if to_user == 'all':
                                print(f"[{from_user}] (ALL): {decrypted_msg}")
                            else:
                                print(f"[{from_user}] (PRIVATE): {decrypted_msg}")
                    except Exception as e:
                        if from_user == 'SYSTEM':
                            # Fallback for system messages
                            try:
                                system_msg = payload.decode('utf-8')
                                print(f"🔔 {system_msg}")
                            except:
                                print(f"🔔 System notification (decode error)")
                        else:
                            print(f"Error decrypting message from {from_user}: {e}")

            elif msg_type == 'file_start':
                from_user = metadata.get('from')
                filename = metadata.get('filename', 'unknown')
                filesize = metadata.get('filesize', 0)

                # Create file for writing
                safe_filename = filename.replace('/', '_').replace('\\', '_')
                filepath = os.path.join('downloads', safe_filename)

                try:
                    file_handle = open(filepath, 'wb')
                    file_transfers[(from_user, filename)] = {
                        'handle': file_handle,
                        'path': filepath,
                        'expected_size': filesize,
                        'received_size': 0
                    }
                    print(f"📥 Receiving file '{filename}' from {from_user} ({filesize} bytes)")
                except Exception as e:
                    print(f"Error creating file '{filename}': {e}")

            elif msg_type == 'file_chunk':
                from_user = metadata.get('from')
                filename = metadata.get('filename', '')
                seq = metadata.get('seq', 0)
                is_last = metadata.get('last', False)

                transfer_key = (from_user, filename)
                if transfer_key in file_transfers and payload:
                    try:
                        decrypted_chunk = fernet.decrypt(payload)
                        transfer = file_transfers[transfer_key]
                        transfer['handle'].write(decrypted_chunk)
                        transfer['received_size'] += len(decrypted_chunk)

                        if is_last:
                            transfer['handle'].close()

                            # Enhanced: File corruption check
                            expected_size = transfer['expected_size']
                            received_size = transfer['received_size']

                            if received_size != expected_size:
                                print(f"❌ [ERROR] File '{filename}' corrupted (expected {expected_size}, got {received_size})")
                            else:
                                print(f"✅ [INFO] File '{filename}' received successfully")

                            print(f"📁 Saved as: {transfer['path']}")
                            del file_transfers[transfer_key]

                    except Exception as e:
                        print(f"Error processing file chunk from {from_user}: {e}")
                        if transfer_key in file_transfers:
                            file_transfers[transfer_key]['handle'].close()
                            del file_transfers[transfer_key]

            elif msg_type == 'list_response':
                users = metadata.get('users', [])
                print(f"👥 Active users ({len(users)}): {', '.join(users)}")

            elif msg_type == 'error':
                error = metadata.get('error', 'unknown_error')
                if error == 'recipient_not_found':
                    print("❌ Error: Recipient not found")
                else:
                    print(f"❌ Server error: {error}")

            else:
                print(f"Unknown message type: {msg_type}")

        except Exception as e:
            print(f"❌ Connection lost: {e}")
            break

    # Clean up open file handles
    for transfer in file_transfers.values():
        try:
            transfer['handle'].close()
        except:
            pass

def main():
    """Main client function."""
    # Get username from user
    username = input("Enter username (leave blank for default 'user'): ").strip()
    if not username:
        username = "user"

    # Connect to server
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        print(f"Connecting to {SERVER_HOST}:{SERVER_PORT}...")
        sock.connect((SERVER_HOST, SERVER_PORT))
        print("Connected to server")

        # Register with server
        if not register_with_server(sock, username):
            return

        # Initialize Fernet cipher
        fernet = Fernet(FERNET_KEY)

        # Start receive thread
        recv_thread = threading.Thread(
            target=recv_loop, 
            args=(sock, username, fernet),
            daemon=True
        )
        recv_thread.start()

        # Run send loop on main thread
        send_loop(sock, username, fernet)

    except KeyboardInterrupt:
        print("\nDisconnecting...")
    except Exception as e:
        print(f"Client error: {e}")
    finally:
        try:
            sock.close()
        except:
            pass

if __name__ == "__main__":
    main()
