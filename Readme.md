# 📧 Async Gmail Client – Python

This Python script uses **Google Gmail API** and **`httpx`** (for asynchronous HTTP requests) to fetch and display Gmail data such as user profile, labels, and the latest 10 emails in a structured and readable format.

---

## 🔧 Features

- OAuth2 authentication using Google's `InstalledAppFlow`
- Asynchronous data fetching via `httpx.AsyncClient`
- Concurrent fetching of:
  - Gmail labels
  - User profile information
  - Recent email messages (up to 10)
- Email parsing to extract:
  - Message ID, Thread ID
  - Timestamp
  - Sender, Subject
  - First 500 characters of message body
- Nicely formatted CLI output

---

## 📂 File Structure

- `credentials.json`: Your OAuth2 credentials from Google Cloud Console
- `token.json`: Auto-generated file storing your access/refresh tokens
- `agent.py`: Main script containing logic for Gmail data fetching

---

## 🧠 Logic & Flow

1. **Authentication**:
   - If `token.json` exists and is valid, it loads credentials.
   - If expired, refreshes token.
   - If no valid token is found, initiates OAuth2 flow using `credentials.json`.

2. **Client Setup**:
   - `AsyncGmailClient` handles all Gmail API interactions.
   - Uses Bearer token in headers for all Gmail API endpoints.

3. **Asynchronous Requests**:
   - Fetches labels, profile, and message list concurrently using `asyncio.gather`.
   - For each message ID, concurrently fetches full message details.

4. **Parsing Emails**:
   - Extracts headers like `From`, `Subject`, and body content from multipart payloads.
   - Decodes base64-encoded email bodies using `urlsafe_b64decode`.

5. **Output**:
   - Profiles, labels, and emails are printed in a structured and readable format.

---

## ✅ Requirements

Install the required packages using:

```bash
    pip install -r requirements.txt
