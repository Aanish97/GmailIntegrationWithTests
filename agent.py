import os.path
import asyncio
from datetime import datetime
from typing import Dict, List, Any
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import httpx

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDENTIALS_FILE = "credentials.json"

GMAIL_FIELDS = [
    "messageId",
    "threadId", 
    "messageTimestamp",
    "labelIds",
    "sender",
    "subject",
    "messageText",
]


class AsyncGmailClient:
    def __init__(self, credentials):
        self.credentials = credentials
        self.base_url = "https://gmail.googleapis.com/gmail/v1"
        
    async def _make_request(self, session: httpx.AsyncClient, endpoint: str, params: Dict = None) -> Dict:
        """Make an authenticated request to Gmail API"""
        headers = {"Authorization": f"Bearer {self.credentials.token}"}
        url = f"{self.base_url}/{endpoint}"
        
        response = await session.get(url, headers=headers, params=params or {})
        response.raise_for_status()
        return response.json()
    
    async def get_labels(self, session: httpx.AsyncClient) -> List[Dict]:
        """Fetch user's labels"""
        data = await self._make_request(session, "users/me/labels")
        return data.get("labels", [])
    
    async def get_profile(self, session: httpx.AsyncClient) -> Dict:
        """Fetch user's profile"""
        return await self._make_request(session, "users/me/profile")
    
    async def get_message_list(self, session: httpx.AsyncClient, max_results: int = 10) -> List[str]:
        """Get list of message IDs"""
        params = {"maxResults": max_results}
        data = await self._make_request(session, "users/me/messages", params)
        messages = data.get("messages", [])
        return [msg["id"] for msg in messages]
    
    async def get_message_details(self, session: httpx.AsyncClient, message_id: str) -> Dict:
        """Get detailed message information"""
        return await self._make_request(session, f"users/me/messages/{message_id}")
    
    def parse_message(self, message_data: Dict) -> Dict:
        """Parse message data to extract required fields"""
        def get_header_value(headers: List[Dict], name: str) -> str:
            for header in headers:
                if header.get("name", "").lower() == name.lower():
                    return header.get("value", "")
            return ""
        
        def extract_text_from_payload(payload: Dict) -> str:
            """Extract text content from message payload"""
            if not payload:
                return ""
            
            # If it's a multipart message
            if "parts" in payload:
                text_parts = []
                for part in payload["parts"]:
                    if part.get("mimeType") == "text/plain":
                        body_data = part.get("body", {}).get("data", "")
                        if body_data:
                            import base64
                            try:
                                decoded = base64.urlsafe_b64decode(body_data + "===").decode('utf-8')
                                text_parts.append(decoded)
                            except:
                                pass
                return "\n".join(text_parts)
            
            # If it's a simple message
            elif payload.get("mimeType") == "text/plain":
                body_data = payload.get("body", {}).get("data", "")
                if body_data:
                    import base64
                    try:
                        return base64.urlsafe_b64decode(body_data + "===").decode('utf-8')
                    except:
                        pass
            
            return ""
        
        headers = message_data.get("payload", {}).get("headers", [])
        
        return {
            "messageId": message_data.get("id", ""),
            "threadId": message_data.get("threadId", ""),
            "messageTimestamp": datetime.fromtimestamp(
                int(message_data.get("internalDate", "0")) / 1000
            ).strftime("%Y-%m-%d %H:%M:%S") if message_data.get("internalDate") else "",
            "labelIds": message_data.get("labelIds", []),
            "sender": get_header_value(headers, "From"),
            "subject": get_header_value(headers, "Subject"),
            "messageText": extract_text_from_payload(message_data.get("payload", {}))[:500] + "..." if len(extract_text_from_payload(message_data.get("payload", {}))) > 500 else extract_text_from_payload(message_data.get("payload", {}))
        }


async def fetch_gmail_data_async(credentials) -> Dict[str, Any]:
    """
    Fetch user's labels, profile, and last 10 emails concurrently
    """
    client = AsyncGmailClient(credentials)
    
    async with httpx.AsyncClient(timeout=30.0) as session:
        # Start all requests concurrently
        labels_task = client.get_labels(session)
        profile_task = client.get_profile(session)
        message_ids_task = client.get_message_list(session, 10)
        
        # Wait for labels, profile, and message IDs
        labels, profile, message_ids = await asyncio.gather(
            labels_task, profile_task, message_ids_task
        )
        
        # Fetch all message details concurrently
        message_tasks = [
            client.get_message_details(session, msg_id) 
            for msg_id in message_ids
        ]
        
        message_details = await asyncio.gather(*message_tasks)
        
        # Parse messages to required format
        parsed_messages = [client.parse_message(msg) for msg in message_details]
        
        return {
            "labels": labels,
            "profile": profile,
            "emails": parsed_messages
        }


def format_output(data: Dict[str, Any]) -> str:
    """Format the fetched data nicely"""
    output = []
    
    # Profile information
    profile = data["profile"]
    output.append("=" * 60)
    output.append("USER PROFILE")
    output.append("=" * 60)
    output.append(f"Email Address: {profile.get('emailAddress', 'N/A')}")
    output.append(f"Messages Total: {profile.get('messagesTotal', 'N/A')}")
    output.append(f"Threads Total: {profile.get('threadsTotal', 'N/A')}")
    output.append(f"History ID: {profile.get('historyId', 'N/A')}")
    output.append("")
    
    # Labels
    output.append("=" * 60)
    output.append("LABELS")
    output.append("=" * 60)
    for label in data["labels"]:
        label_type = label.get("type", "user")
        output.append(f"• {label['name']} ({label_type})")
    output.append("")
    
    # Emails
    output.append("=" * 60)
    output.append("LAST 10 EMAILS")
    output.append("=" * 60)
    
    for i, email in enumerate(data["emails"], 1):
        output.append(f"\n📧 EMAIL #{i}")
        output.append("-" * 40)
        output.append(f"Message ID: {email['messageId']}")
        output.append(f"Thread ID: {email['threadId']}")
        output.append(f"Timestamp: {email['messageTimestamp']}")
        output.append(f"From: {email['sender']}")
        output.append(f"Subject: {email['subject']}")
        output.append(f"Labels: {', '.join(email['labelIds']) if email['labelIds'] else 'None'}")
        output.append(f"Preview: {email['messageText'][:100]}{'...' if len(email['messageText']) > 100 else ''}")
        output.append("")
    
    return "\n".join(output)


async def main():
    """Main function with authentication and data fetching"""
    creds = None

    # Load existing credentials
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # Refresh or get new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"Error: {CREDENTIALS_FILE} not found!")
                print("Please download your OAuth 2.0 credentials from Google Cloud Console")
                print("and save them as 'credentials.json' in this directory.")
                return
            
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=8080)
            
        # Save credentials for future use
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        print("🚀 Fetching Gmail data asynchronously...")
        start_time = asyncio.get_event_loop().time()
        
        # Fetch all data concurrently
        data = await fetch_gmail_data_async(creds)
        
        end_time = asyncio.get_event_loop().time()
        print(f"✅ Data fetched in {end_time - start_time:.2f} seconds")
        print("\n" + format_output(data))
        
    except HttpError as error:
        print(f"An error occurred: {error}")
    except Exception as error:
        print(f"Unexpected error: {error}")


if __name__ == "__main__":
    # Install required dependency: pip install httpx
    asyncio.run(main())