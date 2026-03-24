"""
Root Cause Analysis (RCA) Module
Analyzes errors using AI to generate comprehensive RCA reports
"""

import os
import sys
import logging
from typing import Optional, Dict, Any

# Add workspace root to Python path
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))

from connections.ai_connections import AIClient

logger = logging.getLogger(__name__)


class RCAAnalyzer:
    """Generates Root Cause Analysis for errors using AI"""

    def __init__(self):
        """Initialize RCA analyzer with AI client"""
        self.ai_client = AIClient()
        self.prompt_template_path = os.path.join(workspace_root, 'prompts', 'rca_default.txt')

    def load_prompt_template(self) -> str:
        """Load the RCA prompt template from file"""
        try:
            if not os.path.exists(self.prompt_template_path):
                logger.error(f"Prompt template not found at: {self.prompt_template_path}")
                return self._get_default_prompt()
            
            with open(self.prompt_template_path, 'r', encoding='utf-8') as f:
                template = f.read()
            logger.info("RCA prompt template loaded successfully")
            return template
        except Exception as e:
            logger.error(f"Failed to load prompt template: {e}")
            return self._get_default_prompt()

    @staticmethod
    def _get_default_prompt() -> str:
        """Return default RCA prompt if file loading fails"""
        return """# Root Cause Analysis Prompt

You are an expert root cause analysis specialist. Analyze the provided error information and perform a comprehensive root cause analysis.

## Analysis Framework:
1. **Error Pattern Recognition**: Identify patterns in error occurrence
2. **System Component Analysis**: Examine affected system components
3. **Timeline Reconstruction**: Create a timeline of events leading to the error
4. **Root Cause Identification**: Determine the primary root cause
5. **Contributing Factors**: Identify secondary factors that contributed

## Output Format:
- Primary Cause
- Contributing Factors (list)
- Severity Assessment

Error Details: {error_details}
System Context: {system_context}
"""

    def generate_rca(self, error_data: Dict[str, Any], system_context: str = "") -> Optional[str]:
        """
        Generate Root Cause Analysis for an error
        
        Args:
            error_data: Dictionary containing error details (message, stack_trace, error_tool, etc.)
            system_context: Optional system context information
            
        Returns:
            RCA analysis from AI, or None if generation fails
        """
        try:
            # Load prompt template
            prompt_template = self.load_prompt_template()
            
            # Format error details
            error_details = self._format_error_details(error_data)
            
            if error_details:
            # Append error details to prompt
                final_prompt = prompt_template.format(
                    error_details=error_details,
                    system_context=system_context if system_context else "No additional system context provided"
                )
            else:
                logger.warning("No error details provided for RCA analysis")
                return None
            
            logger.info(f"Sending RCA analysis request to AI for error: {error_data.get('error_id', 'Unknown')}")
            
            # Call AI to generate RCA
            rca_response = self.ai_client.generate_text(
                prompt=final_prompt,
                max_tokens=2000,
                temperature=0.3  # Lower temperature for more focused RCA analysis
            )
            
            if rca_response:
                logger.info("RCA analysis generated successfully")
                return rca_response
            else:
                logger.error("AI failed to generate RCA. Error details: " + str(self.ai_client.last_error_info()))
                return None
                
        except Exception as e:
            logger.error(f"Exception in RCA generation: {e}")
            return None

    @staticmethod
    def _format_error_details(error_data: Dict[str, Any]) -> str:
        """
        Format error details dictionary into readable string
        
        Args:
            error_data: Dictionary with error information
            
        Returns:
            Formatted error details string
        """
        logger.info("Formatting error details for RCA analysis")

        details = []

        # Map common error fields
        field_mapping = {
            'error_message': 'Error Message',
            'error_tool': 'Error Tool/Component',
            'stack_trace': 'Stack Trace',
            'environment': 'Environment',
            'affected_service': 'Affected Service',
            'error_code': 'Error Code',
            'user_action': 'User Action',
            'logs': 'Additional Logs'
        }
        
        for key, label in field_mapping.items():
            if key in error_data and error_data[key]:
                details.append(f"{label}: {error_data[key]}")
        
        # Add any additional fields not in mapping
        for key, value in error_data.items():
            if key not in field_mapping and value:
                details.append(f"{key.replace('_', ' ').title()}: {value}")
        if not details:
            details.append("No error details provided.")
            return False
        
        return "\n".join(details) if details else "No error details provided"
    
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    rca_analyzer = RCAAnalyzer()
    sample_error_data = {
        'error_message': 'Database connection timeout',
        'error_tool': 'PostgreSQL',
        'stack_trace': 'ConnectionError at line 45 in db_connector.py',
        'environment': 'Production',
        'affected_service': 'User Authentication Service',
        'error_code': 'DB_CONN_TIMEOUT',
        'user_action': 'Login attempt'
    }
    rca_result = rca_analyzer.generate_rca(sample_error_data, system_context="Occurred during peak traffic hours")