
"""
Encrypted Terminal Chat Client - Enhanced Version
Usage: python client.py
"""

import socket
import threading
import json
import struct
import os
import base64
from cryptography.fernet import Fernet

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5000
FERNET_KEY = b'ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg='
CHUNK_SIZE = 4096


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

def register_with_server(sock, username):
    send_framed(sock, {"type": "register", "from": username})
    response_meta, _ = recv_message(sock)

    if response_meta.get('type') == 'error':
        error = response_meta.get('error', 'unknown_error')
        if error == 'username_taken':
            print("Error: Username is already taken. Please choose a different name.")
        elif error == 'invalid_username':
            print("Error: Invalid username provided.")
        else:
            print(f"Error: {error}")
        return False, False
    elif response_meta.get('type') == 'register_success':
        message = response_meta.get('message', f'Registered as {username}')
        is_admin = response_meta.get('is_admin', False)
        print(message)
        if is_admin:
            print("🔑 You are now the chat administrator!")
        return True, is_admin
    else:
        print("Unexpected server response during registration")
        return False, False

def send_loop(sock, username, fernet, is_admin=False):
    print("Type /help for commands")
    if is_admin:
        print("🔑 Admin commands: /admin_history")

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
                if is_admin:
                    print("  /admin_history        - View chat history (Admin only)")

            elif user_input == '/list':
                send_framed(sock, {"type": "list_request", "from": username})

            elif user_input == '/admin_history' and is_admin:
                send_framed(sock, {"type": "admin_history", "from": username})

            elif user_input.startswith('/all '):
                message = user_input[5:]
                if message:
                    encrypted_payload = fernet.encrypt(message.encode('utf-8'))
                    send_framed(sock, {"type": "msg", "from": username, "to": "all"}, encrypted_payload)
                else:
                    print("Usage: /all <message>")

            elif user_input.startswith('/msg '):
                parts = user_input[5:].split(' ', 1)
                if len(parts) >= 2:
                    target_user, message = parts
                    encrypted_payload = fernet.encrypt(message.encode('utf-8'))
                    send_framed(sock, {"type": "msg", "from": username, "to": target_user}, encrypted_payload)
                else:
                    print("Usage: /msg <user> <message>")

            elif user_input.startswith('/file '):
                parts = user_input[6:].split(' ', 1)
                if len(parts) >= 2:
                    target_user, filepath = parts
                    if not os.path.exists(filepath):
                        print(f"Error: File '{filepath}' not found")
                        continue
                    try:
                        filename = os.path.basename(filepath)
                        filesize = os.path.getsize(filepath)
                        send_framed(sock, {"type": "file_start", "from": username, "to": target_user, "filename": filename, "filesize": filesize})
                        with open(filepath, 'rb') as file:
                            seq = 1
                            while True:
                                chunk = file.read(CHUNK_SIZE)
                                if not chunk:
                                    break
                                encrypted_chunk = fernet.encrypt(chunk)
                                is_last = len(chunk) < CHUNK_SIZE
                                send_framed(sock, {"type": "file_chunk", "from": username, "to": target_user, "filename": filename, "seq": seq, "last": is_last}, encrypted_chunk)
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

def recv_loop(sock, username, fernet):
    os.makedirs('downloads', exist_ok=True)
    file_transfers = {}

    while True:
        try:
            metadata, payload = recv_message(sock)
            msg_type = metadata.get('type')

            if msg_type == 'msg':
                from_user = metadata.get('from')
                to_user = metadata.get('to')

                if payload:
                    try:
                        if from_user == 'SYSTEM':
                            system_msg = payload.decode('utf-8')
                            print(f"🔔 {system_msg}")
                        else:
                            decrypted_msg = fernet.decrypt(payload).decode('utf-8')
                            if to_user == 'all':
                                print(f"[{from_user}] (ALL): {decrypted_msg}")
                            else:
                                print(f"[{from_user}] (PRIVATE): {decrypted_msg}")
                    except Exception as e:
                        if from_user == 'SYSTEM':
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

                safe_filename = filename.replace('/', '_').replace('\\', '_')
                filepath = os.path.join('downloads', safe_filename)
                try:
                    file_handle = open(filepath, 'wb')
                    file_transfers[(from_user, filename)] = {'handle': file_handle, 'path': filepath, 'expected_size': filesize, 'received_size': 0}
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

            elif msg_type == 'admin_history_response':
                messages = metadata.get('messages', [])
                print("\n🔍 === ADMIN CHAT HISTORY ===")
                if not messages:
                    print("No chat history available.")
                else:
                    for msg in messages:
                        timestamp = msg.get('timestamp', 'Unknown')
                        from_user = msg.get('from', 'Unknown')
                        to_user = msg.get('to', 'Unknown')
                        message = msg.get('message', '')
                        if to_user == 'all':
                            print(f"[{timestamp}] {from_user} → ALL: {message}")
                        else:
                            print(f"[{timestamp}] {from_user} → {to_user}: {message}")
                print("=== END HISTORY ===\n")

            elif msg_type == 'error':
                error = metadata.get('error', 'unknown_error')
                if error == 'recipient_not_found':
                    print("❌ Error: Recipient not found")
                elif error == 'admin_privileges_required':
                    print("❌ Error: Admin privileges required for this command")
                else:
                    print(f"❌ Server error: {error}")

            else:
                print(f"Unknown message type: {msg_type}")

        except Exception as e:
            print(f"❌ Connection lost: {e}")
            break

    for transfer in file_transfers.values():
        try:
            transfer['handle'].close()
        except:
            pass

def main():
    username = input("Enter username (leave blank for default 'user'): ").strip()
    if not username:
        username = "user"
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        print(f"Connecting to {SERVER_HOST}:{SERVER_PORT}...")
        sock.connect((SERVER_HOST, SERVER_PORT))
        print("Connected to server")
        success, is_admin = register_with_server(sock, username)
        if not success:
            return
        fernet = Fernet(FERNET_KEY)
        threading.Thread(target=recv_loop, args=(sock, username, fernet), daemon=True).start()
        send_loop(sock, username, fernet, is_admin)

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
