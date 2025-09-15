"""
Health Check Middleware for AWS Elastic Beanstalk
Handles health check requests before ALLOWED_HOSTS validation to prevent DisallowedHost errors.
"""

from django.http import HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class HealthCheckMiddleware(MiddlewareMixin):
    """
    Middleware to handle AWS health check requests before ALLOWED_HOSTS validation.
    
    This prevents DisallowedHost errors when AWS load balancers or health check services
    access the application from IPs not in ALLOWED_HOSTS.
    """
    
    def process_request(self, request):
        """
        Process incoming requests and handle health checks early.
        """
        path = request.META.get("PATH_INFO", "")
        
        # Check if this is a health check request
        if self.is_health_check_request(request, path):
            logger.debug(f"Health check request detected from {request.META.get('REMOTE_ADDR', 'unknown')}")
            return self.handle_health_check(request)
        
        return None  # Continue normal processing
    
    def is_health_check_request(self, request, path):
        """
        Determine if this is a health check request.
        """
        # Check for common health check patterns
        health_check_paths = ["/", "/ping/", "/health/", "/healthcheck/", "/status/"]
        
        # AWS ELB often uses the root path for health checks
        if path == "/" and self.looks_like_health_check(request):
            return True
            
        # Check explicit health check paths
        if path in health_check_paths:
            return True
            
        return False
    
    def looks_like_health_check(self, request):
        """
        Determine if a root path request looks like a health check.
        """
        # Health checks typically:
        # 1. Use GET method
        # 2. Have minimal headers
        # 3. Don't have cookies/sessions
        # 4. Come from specific User-Agent patterns
        
        if request.method != "GET":
            return False
            
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        # AWS ELB health check user agents
        aws_health_check_agents = [
            'elb-healthchecker',
            'amazonelb',
            'aws-elb',
            'aws internal'
        ]
        
        if any(agent in user_agent for agent in aws_health_check_agents):
            return True
            
        # Check if request has minimal headers (typical of health checks)
        header_count = len([k for k in request.META.keys() if k.startswith('HTTP_')])
        if header_count <= 3:  # Very few headers = likely health check
            return True
            
        # Check for lack of cookies (health checks don't usually have them)
        if not request.COOKIES and not request.META.get('HTTP_COOKIE'):
            return True
            
        return False
    
    def handle_health_check(self, request):
        """
        Handle the health check request with appropriate response.
        """
        try:
            # Perform basic health checks
            health_status = self.perform_health_checks()
            
            if health_status['healthy']:
                # Return simple response for basic health checks
                if request.META.get("PATH_INFO") in ["/ping/", "/health/"]:
                    return JsonResponse(health_status)
                else:
                    # For root path, return minimal HTML (what ELB expects)
                    return HttpResponse(
                        "OK", 
                        content_type="text/plain",
                        status=200
                    )
            else:
                return HttpResponse(
                    "Service Unavailable", 
                    content_type="text/plain",
                    status=503
                )
                
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return HttpResponse(
                "Health Check Error", 
                content_type="text/plain",
                status=503
            )
    
    def perform_health_checks(self):
        """
        Perform actual health checks - customize based on your needs.
        """
        health_status = {
            'healthy': True,
            'checks': {}
        }
        
        try:
            # Database connectivity check
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                health_status['checks']['database'] = 'ok'
        except Exception as e:
            health_status['healthy'] = False
            health_status['checks']['database'] = f'error: {str(e)}'
            
        try:
            # Cache connectivity check (if using cache)
            from django.core.cache import cache
            cache.set('health_check', 'ok', 30)
            if cache.get('health_check') == 'ok':
                health_status['checks']['cache'] = 'ok'
            else:
                health_status['checks']['cache'] = 'warning: cache not responding'
        except Exception as e:
            # Cache errors are often non-critical
            health_status['checks']['cache'] = f'warning: {str(e)}'
            
        return health_status
