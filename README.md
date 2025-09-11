
# Python Encrypted Chatroom

A **terminal-based encrypted chatroom** built using Python sockets.  
It supports **multi-client messaging, private messages, file sharing with corruption detection, and encryption demonstration**.  

This was developed as a **course-end project for Computer Networks**.

---

## 🚀 Features
- **Multi-client chat** – many users can connect at once.
- **Broadcast chat** – send a message to everyone (`/all <msg>`).
- **Private chat** – send direct messages (`/msg <user> <msg>`).
- **File sharing** – transfer files securely with corruption detection.
- **Encryption demo** – all data is encrypted using Fernet (AES + HMAC); server logs show encrypted Base64 payloads.
- **System notifications** – join/leave messages.
- **Admin tag** – the first connected user is labeled `[ADMIN]` (for display only).

---

## 🛠️ Tech Stack
- **Language:** Python 3
- **Libraries:** `socket`, `threading`, `cryptography`
- **Interface:** Terminal only (no HTML/GUI)

---

## 📂 Project Structure
```

│
├── server.py   # Starts the server, manages clients, relays messages/files
├── client.py   # Connects to server, sends/receives encrypted messages & files
└── README.md   # Project documentation

````

---

## ⚡ How to Run

### 1. Start the Server
```bash
python server.py
````

### 2. Run Clients (in separate terminals or PCs on the same network)

```bash
python client.py
```

### 3. Enter Username

* First user = `[ADMIN]`
* Others = normal users

---

## 💬 Commands

Inside the client:

```
/all <message>         → Broadcast to all users
/msg <user> <message>  → Send private message
/file <user> <path>    → Send a file
/list                  → Show active users
/quit                  → Disconnect
/help                  → Show help
```

---

## 🔐 Encryption Demonstration

* All chat and file data is encrypted with **Fernet** before sending.
* The server logs each payload as **Base64-encoded ciphertext** to show backend security.

Example server log:

```
[META] 2025-09-11 12:45:00 | type=msg | from=Alice | to=all
[ENCRYPTED_PAYLOAD_BASE64] gAAAAABl...
```

---

## 📂 File Sharing

* Files are sent in encrypted chunks.
* The receiver stores them in a **downloads/** folder.
* File corruption is checked (`expected size vs received size`).

---

## 🎯 Learning Outcomes

* TCP socket programming in Python
* Multi-threaded server/client architecture
* Secure communication with symmetric encryption
* File transfer with error detection
* System/user role handling

---

## 📜 License

This project is for **academic learning purposes**.
You may reuse or modify it for educational use.
