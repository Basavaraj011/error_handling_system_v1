"""
Microsoft Teams Notification Client
"""

import requests
import logging
from config.settings import TEAMS_WORKFLOW_URL
logger = logging.getLogger(__name__)


def send_teams_notification(ticket_key: str, summary: str, pr:bool = False) -> bool:
    """
    Send notification to Microsoft Teams channel
    """

    try:
        if pr:
            header = f"New PR Createdd: {ticket_key}"
        else:
            header = f"New Jira Ticket Created: {ticket_key}"
        message_card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "summary": header,
            "themeColor": "0076D7",
            "title": header,
            "sections": [
                {
                    "activityTitle": f"Ticket: {ticket_key}",
                    "facts": [
                        {"name": "Summary", "value": summary},
                        {"name": "Status", "value": "Created"},
                    ],
                    "markdown": True
                }
            ]
        }

        response = requests.post(
            TEAMS_WORKFLOW_URL,
            json=message_card,
            timeout=10
        )

        if response.status_code == 202:
            logger.info("Teams notification sent successfully")
            return True
        else:
            logger.error(f"Failed to send Teams notification: {response.text}")
            return False

    except Exception as e:
        logger.error(f"Error sending Teams notification: {e}")
        return False
