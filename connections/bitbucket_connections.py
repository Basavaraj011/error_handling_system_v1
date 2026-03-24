"""
Bitbucket client for repository and PR management
"""
from atlassian import Bitbucket
from config.settings import BITBUCKET_URL, BITBUCKET_USERNAME, BITBUCKET_APP_PASSWORD
import logging

logger = logging.getLogger(__name__)


class BitbucketClient:
    """Client for interacting with Bitbucket"""
    
    def __init__(self, url: str = BITBUCKET_URL, username: str = BITBUCKET_USERNAME, password: str = BITBUCKET_APP_PASSWORD):
        self.url = url
        self.username = username
        self.password = password
        self.client = None
        self._connect()
    
    def _connect(self) -> None:
        """Establish connection to Bitbucket"""
        try:
            self.client = Bitbucket(url=self.url, username=self.username, password=self.password)
            logger.info("Connected to Bitbucket")
        except Exception as e:
            logger.error(f"Failed to connect to Bitbucket: {e}")
    
    def create_pull_request(self, workspace: str, repo: str, source_branch: str, target_branch: str, title: str, description: str) -> str:
        """Create a pull request"""
        try:
            pr = self.client.pull_request_create(
                workspace=workspace,
                repo_slug=repo,
                source_branch=source_branch,
                destination_branch=target_branch,
                title=title,
                description=description
            )
            logger.info(f"Created pull request: {pr}")
            return pr
        except Exception as e:
            logger.error(f"Failed to create pull request: {e}")
            return None
    
    def get_file(self, workspace: str, repo: str, filepath: str, branch: str = "main") -> str:
        """Get file content from repository"""
        try:
            content = self.client.get_file(
                workspace=workspace,
                repo_slug=repo,
                filepath=filepath,
                branch=branch
            )
            return content
        except Exception as e:
            logger.error(f"Failed to get file: {e}")
            return None
    
    def commit_file(self, workspace: str, repo: str, filepath: str, content: str, branch: str, message: str) -> bool:
        """Commit a file to repository"""
        try:
            self.client.commit_file(
                workspace=workspace,
                repo_slug=repo,
                filepath=filepath,
                content=content,
                branch=branch,
                message=message
            )
            logger.info(f"Committed file: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to commit file: {e}")
            return False
