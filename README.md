

# Python Encrypted Chatroom

A **terminal-based encrypted chatroom** built using Python sockets.
It supports **multi-client messaging, private messages, file sharing with corruption detection, and encryption demonstration**.

This was developed as a **course-end project for Computer Networks**.

---

## 🚀 Features

* **Multi-client chat** – many users can connect at once.
* **Broadcast chat** – send a message to everyone (`/all <msg>`).
* **Private chat** – send direct messages (`/msg <user> <msg>`).
* **File sharing** – transfer files securely with corruption detection.
* **Encryption demo** – all data is encrypted using Fernet (AES + HMAC); server logs show encrypted Base64 payloads.
* **System notifications** – join/leave messages.
* **Admin tag** – the first connected user is labeled `[ADMIN]` (for display only).

---

## 🛠️ Tech Stack

* **Language:** Python 3
* **Libraries:** `socket`, `threading`, `cryptography`, `os`, `sys`
* **Interface:** Terminal only (no HTML/GUI)

---

## 📂 Project Structure

```

├── server.py        # Starts the server, manages clients, relays messages/files
├── client.py        # Connects to server, sends/receives encrypted messages & files
├── README.md        # Project documentation
├── .gitignore       # Ensures secret keys and temp files are not pushed
└── (hidden) \~/.chat\_fernet.key   # Fernet encryption key (created by user, never committed)

```

---

## ⚡ How to Run

### 1. Start the Server

```bash
python server.py
```

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


## 🔑 Encryption Key Setup

This chatroom uses **Fernet (AES + HMAC)** for encrypting all messages and files.  
To keep the key secure, it is stored in a hidden file on your system instead of inside the code.

### 1. Generate a Fernet Key

Run this Python snippet once to generate a key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
````

You’ll see output like:

```
<YOUR_GENERATED_KEY_HERE>
```

---

### 2. Create the Key File

Save the generated key into a hidden file in your home directory:

```bash
echo "<YOUR_GENERATED_KEY_HERE>" > ~/.chat_fernet.key
```


👉 The file must contain **only the key on a single line** (no spaces or extra lines).

---

### 3. Keep It Secure

* Do **not share** your `.chat_fernet.key` file.
* Do **not commit** it to GitHub (already covered by `.gitignore`).
* If the key is leaked, **anyone can decrypt all chat messages and files**.


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

