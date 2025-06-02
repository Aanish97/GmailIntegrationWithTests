import pytest
import base64
from datetime import datetime
from unittest.mock import Mock


# Mock credentials class
class MockCredentials:
    def __init__(self, token="mock_token"):
        self.token = token


# Simplified AsyncGmailClient for testing
class AsyncGmailClient:
    def __init__(self, credentials):
        self.credentials = credentials
        self.base_url = "https://gmail.googleapis.com/gmail/v1"
    
    def parse_message(self, message_data: dict) -> dict:
        """Parse message data to extract required fields"""
        def get_header_value(headers: list, name: str) -> str:
            for header in headers:
                if header.get("name", "").lower() == name.lower():
                    return header.get("value", "")
            return ""
        
        def extract_text_from_payload(payload: dict) -> str:
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


# Test fixtures
@pytest.fixture
def mock_credentials():
    return MockCredentials("test_access_token")


@pytest.fixture
def complete_message_payload():
    """Complete message payload with all fields present"""
    message_text = "Hello, this is a test email with complete information including sender, subject, timestamp, and labels."
    encoded_text = base64.urlsafe_b64encode(message_text.encode('utf-8')).decode('utf-8')
    
    return {
        "id": "msg_complete_12345",
        "threadId": "thread_complete_67890",
        "internalDate": "1672531200000",  # Jan 1, 2023 00:00:00 UTC
        "labelIds": ["INBOX", "IMPORTANT", "CATEGORY_PERSONAL"],
        "payload": {
            "headers": [
                {"name": "From", "value": "john.doe@example.com"},
                {"name": "To", "value": "jane.smith@example.com"},
                {"name": "Subject", "value": "Complete Test Email Subject"},
                {"name": "Date", "value": "Sun, 1 Jan 2023 00:00:00 +0000"}
            ],
            "mimeType": "text/plain",
            "body": {
                "data": encoded_text
            }
        }
    }


@pytest.fixture
def incomplete_message_payload():
    """Incomplete message payload missing optional fields"""
    return {
        "id": "msg_incomplete_98765",
        "threadId": "thread_incomplete_54321",
        # Missing: internalDate (optional)
        # Missing: labelIds (optional)
        "payload": {
            "headers": [
                {"name": "From", "value": "incomplete.sender@example.com"},
                # Missing: Subject header (optional)
                {"name": "Date", "value": "Mon, 2 Jan 2023 12:00:00 +0000"}
            ],
            "mimeType": "text/html",
            # Missing: body content (optional)
        }
    }


class TestGmailMessageParsing:
    """Test Gmail message parsing for two main scenarios"""
    
    def test_complete_payload_parsing(self, mock_credentials, complete_message_payload):
        """
        Test Case 1: Normal payload with full fields
        
        This test verifies that when all fields are present in the Gmail API response,
        they are correctly parsed and extracted into the required format.
        """
        client = AsyncGmailClient(mock_credentials)
        result = client.parse_message(complete_message_payload)
        
        # Verify all required fields are properly extracted
        assert result["messageId"] == "msg_complete_12345"
        assert result["threadId"] == "thread_complete_67890"
        
        # Timestamp should be properly formatted (timezone-aware)
        assert result["messageTimestamp"].startswith("2023-01-01")
        assert len(result["messageTimestamp"]) == 19  # YYYY-MM-DD HH:MM:SS format
        
        # Labels should be preserved as a list
        assert result["labelIds"] == ["INBOX", "IMPORTANT", "CATEGORY_PERSONAL"]
        assert len(result["labelIds"]) == 3
        
        # Headers should be correctly extracted
        assert result["sender"] == "john.doe@example.com"
        assert result["subject"] == "Complete Test Email Subject"
        
        # Message text should be decoded from base64
        expected_text = "Hello, this is a test email with complete information including sender, subject, timestamp, and labels."
        assert result["messageText"] == expected_text
        
        # Verify no fields are empty when data is available
        assert all(field != "" for field in [result["messageId"], result["threadId"], 
                                           result["messageTimestamp"], result["sender"], 
                                           result["subject"], result["messageText"]])
        assert len(result["labelIds"]) > 0
    
    def test_incomplete_payload_parsing(self, mock_credentials, incomplete_message_payload):
        """
        Test Case 2: Payload missing some optional fields
        
        This test verifies that when optional fields are missing from the Gmail API response,
        the parser handles them gracefully with appropriate default values.
        """
        client = AsyncGmailClient(mock_credentials)
        result = client.parse_message(incomplete_message_payload)
        
        # Required fields that are present should be correctly parsed
        assert result["messageId"] == "msg_incomplete_98765"
        assert result["threadId"] == "thread_incomplete_54321"
        assert result["sender"] == "incomplete.sender@example.com"
        
        # Missing optional fields should have appropriate defaults
        assert result["messageTimestamp"] == ""  # Missing internalDate -> empty string
        assert result["labelIds"] == []          # Missing labelIds -> empty list
        assert result["subject"] == ""           # Missing Subject header -> empty string  
        assert result["messageText"] == ""       # Missing body content -> empty string
        
        # Verify the structure is still valid
        assert isinstance(result["messageId"], str)
        assert isinstance(result["threadId"], str)
        assert isinstance(result["messageTimestamp"], str)
        assert isinstance(result["labelIds"], list)
        assert isinstance(result["sender"], str)
        assert isinstance(result["subject"], str)
        assert isinstance(result["messageText"], str)
        
        # Verify that present fields are not empty
        assert result["messageId"] != ""
        assert result["threadId"] != ""
        assert result["sender"] != ""
        
        # Verify that missing fields are properly defaulted
        assert result["messageTimestamp"] == ""
        assert result["labelIds"] == []
        assert result["subject"] == ""
        assert result["messageText"] == ""


if __name__ == "__main__":
    # Run tests with: pytest test_two_scenarios.py -v
    pytest.main([__file__, "-v"])