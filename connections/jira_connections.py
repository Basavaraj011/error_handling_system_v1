"""
JIRA client for ticket management
"""
from jira import JIRA
import logging
from config.settings import JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN

logger = logging.getLogger(__name__)


class JiraClient:
    """Client for interacting with JIRA"""
    
    def __init__(self, url: str = JIRA_URL, username: str = JIRA_USERNAME, api_token: str = JIRA_API_TOKEN):
        self.url = url or JIRA_URL
        self.username = username or JIRA_USERNAME
        self.api_token = api_token or JIRA_API_TOKEN
        self.client = None
        self._connect()

        
    
    
    def _connect(self) -> None:
        """Establish connection to JIRA"""
        try:
            self.client = JIRA(server=self.url, basic_auth=(self.username, self.api_token))
            print(f"Connected to JIRA at URL: {self.client.projects()}")
            project = self.client.project('SCRUM')
            issue_types = project.issueTypes    
            print(f"Available issue types in project {project.key}: {[it.name for it in issue_types]}")

        except Exception as e:
            print(f"Failed to connect to JIRA: {e}")
    
    def create_ticket(self, project_key: str, issue_type: str, summary: str, description: str, priority: str = "Medium") -> str:
        """Create a new JIRA ticket"""
        try:
            issue_dict = {
                'project': {'key': project_key},
                'summary': summary,
                'description': description,
                'issuetype': {'name': issue_type},
                'priority': {'name': priority}
            }
            issue = self.client.create_issue(fields=issue_dict)
            logger.info(f"Created JIRA ticket: {issue.key}")
            return issue.key
        except Exception as e:
            logger.error(f"Failed to create JIRA ticket: {e}")
            return None
    
    def get_ticket(self, ticket_key: str):
        """Get a JIRA ticket"""
        try:
            return self.client.issue(ticket_key)
        except Exception as e:
            logger.error(f"Failed to get JIRA ticket: {e}")
            return None
    
    def add_comment(self, ticket_key: str, comment: str) -> bool:
        """Add a comment to a ticket"""
        try:
            self.client.add_comment(ticket_key, comment)
            logger.info(f"Added comment to {ticket_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to add comment: {e}")
            return False
