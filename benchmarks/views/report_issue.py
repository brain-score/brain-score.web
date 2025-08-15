import json
import logging
import requests
from datetime import datetime
from typing import Dict, Any

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from botocore.exceptions import NoCredentialsError

from web.settings import get_secret

logger = logging.getLogger(__name__)

class ReportIssueView(View):
    """
    Handle issue reporting to GitHub repository
    """
    
    # GitHub repository information
    GITHUB_REPO_OWNER = "brain-score"
    GITHUB_REPO_NAME = "brain-score.web"
    GITHUB_API_URL = "https://api.github.com"
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request):
        """Handle POST request to create a GitHub issue"""
        try:
            # Parse request data
            data = json.loads(request.body)
            
            # Validate required fields
            validation_error = self._validate_issue_data(data)
            if validation_error:
                return JsonResponse({
                    'success': False,
                    'error': validation_error
                }, status=400)
            
            # Create GitHub issue
            issue_response = self._create_github_issue(data)
            
            if issue_response['success']:
                logger.info(f"Issue created successfully: {issue_response.get('issue_url')}")
                return JsonResponse({
                    'success': True,
                    'message': 'Issue submitted successfully',
                    'issue_url': issue_response.get('issue_url'),
                    'issue_number': issue_response.get('issue_number')
                })
            else:
                logger.error(f"Failed to create GitHub issue: {issue_response.get('error')}")
                return JsonResponse({
                    'success': False,
                    'error': issue_response.get('error', 'Failed to create issue')
                }, status=500)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.exception("Unexpected error in report issue view")
            return JsonResponse({
                'success': False,
                'error': 'An unexpected error occurred'
            }, status=500)
    
    def _validate_issue_data(self, data: Dict[str, Any]) -> str:
        """Validate the issue data and return error message if invalid"""
        
        required_fields = ['issue_type', 'title', 'description']
        for field in required_fields:
            if not data.get(field, '').strip():
                return f'Missing required field: {field}'
        
        # Validate title length
        title = data.get('title', '').strip()
        if len(title) < 10:
            return 'Title must be at least 10 characters long'
        if len(title) > 100:
            return 'Title must be no more than 100 characters long'
        
        # Validate description length
        description = data.get('description', '').strip()
        if len(description) < 20:
            return 'Description must be at least 20 characters long'
        if len(description) > 5000:
            return 'Description must be no more than 5000 characters long'
        
        # Validate issue type
        valid_types = ['bug', 'feature', 'data', 'performance', 'ui', 'other']
        if data.get('issue_type') not in valid_types:
            return f'Invalid issue type. Must be one of: {", ".join(valid_types)}'
        
        # Validate email format if provided
        email = data.get('contact_email', '').strip()
        if email and '@' not in email:
            return 'Invalid email format'
        
        return None
    
    def _create_github_issue(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a GitHub issue and return the response"""
        
        try:
            # Get GitHub token from AWS secrets
            github_token = self._get_github_token()
            if not github_token:
                return {
                    'success': False,
                    'error': 'GitHub authentication not available'
                }
            
            # Prepare issue data
            issue_data = self._prepare_issue_data(data)
            
            # Make API call to GitHub
            response = self._make_github_api_request(github_token, issue_data)
            
            if response.status_code == 201:
                issue_info = response.json()
                return {
                    'success': True,
                    'issue_url': issue_info.get('html_url'),
                    'issue_number': issue_info.get('number')
                }
            else:
                error_msg = 'GitHub API error'
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', error_msg)
                except:
                    pass
                
                return {
                    'success': False,
                    'error': f'{error_msg} (Status: {response.status_code})'
                }
                
        except requests.RequestException as e:
            logger.exception("GitHub API request failed")
            return {
                'success': False,
                'error': 'Failed to connect to GitHub API'
            }
        except Exception as e:
            logger.exception("Unexpected error creating GitHub issue")
            return {
                'success': False,
                'error': 'Unexpected error occurred'
            }
    
    def _get_github_token(self) -> str:
        """Get GitHub token from AWS secrets or settings"""
        try:
            # Try to get from AWS secrets first
            secrets = get_secret("web-access-github", settings.REGION_NAME)
            return secrets.get('github-token', '')
        except NoCredentialsError:
            logger.warning("AWS credentials not available for GitHub token retrieval")
        except Exception as e:
            logger.warning(f"Could not retrieve GitHub token from AWS secrets: {e}")
            
        # Fallback to Django settings (for development)
        github_token = getattr(settings, 'GITHUB_TOKEN', '')
        if github_token:
            return github_token
            
        # Final fallback to environment variable
        import os
        env_token = os.getenv('GITHUB_TOKEN', '')
        if env_token:
            logger.info("Using GitHub token from environment variable")
            return env_token
            
        logger.error("No GitHub token found in AWS secrets, Django settings, or environment variables")
        return ''
    
    def _prepare_issue_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare the issue data for GitHub API"""
        
        # Map issue types to labels and metadata
        issue_type_mapping = {
            'bug': {'label': 'bug', 'template': 'Bug Report', 'prefix': '[BUG]'},
            'feature': {'label': 'enhancement', 'template': 'Feature Request', 'prefix': '[FEATURE]'},
            'data': {'label': 'data', 'template': 'Benchmark Issue', 'prefix': '[BENCHMARK]'},
            'ui': {'label': 'ui/ux', 'template': 'UI/UX Issue', 'prefix': '[UI/UX]'},
            'other': {'label': 'other', 'template': 'General Issue', 'prefix': '[OTHER]'}
        }
        
        issue_type = data.get('issue_type', 'other')
        type_info = issue_type_mapping.get(issue_type, issue_type_mapping['other'])
    
        # Text prefixes like [BUG], [FEATURE], etc.
        title = f"{type_info['prefix']} {data['title'].strip()}"
        
        # Prepare description with metadata
        description_parts = [
            f"## {type_info['template']}",
            "",
            "### Description",
            data['description'].strip(),
            "",
            "",
            "### Technical Details",
            f"- **Page URL**: {data.get('page_url', 'Not provided')}",
            f"- **Timestamp**: {data.get('timestamp', datetime.now().isoformat())}",
            f"- **User Agent**: {data.get('user_agent', 'Not provided')}",
        ]
        
        # Add system info if available
        system_info = data.get('system_info', '').strip()
        if system_info:
            description_parts.extend([
                f"- **System Info**: {system_info}",
            ])
        
        # Add filter state if available
        filter_state = data.get('filter_state')
        if filter_state:
            description_parts.extend([
                "",
                "### Current Filter State",
                f"- **Search Term**: `{filter_state.get('search_term', 'None')}`",
                f"- **Visible Rows**: {filter_state.get('visible_rows', 'Unknown')}",
                f"- **Active Filters**: {json.dumps(filter_state.get('active_filters', {}), indent=2)}"
            ])
        

        
        # Add contact info if provided
        contact_email = data.get('contact_email', '').strip()
        if contact_email:
            description_parts.extend([
                "",
                f"### Contact",
                f"- **Email**: {contact_email}"
            ])
        
        description_parts.extend([
            "",
            "---",
            "*This issue was automatically generated from the Brain-Score website.*"
        ])
        
        return {
            'title': title,
            'body': '\n'.join(description_parts),
            'labels': [type_info['label'], 'auto-generated']
        }
    

    
    def _make_github_api_request(self, token: str, issue_data: Dict[str, Any]) -> requests.Response:
        """Make the actual API request to GitHub"""
        
        url = f"{self.GITHUB_API_URL}/repos/{self.GITHUB_REPO_OWNER}/{self.GITHUB_REPO_NAME}/issues"
        
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
            'User-Agent': 'Brain-Score-Website/1.0'
        }
        
        return requests.post(
            url,
            headers=headers,
            json=issue_data,
            timeout=30
        )


# Create the view instance for URL mapping
report_issue_view = ReportIssueView.as_view()
