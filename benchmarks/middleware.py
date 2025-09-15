"""
AWS health checks come from dynamic, changing IP addresses. 
We tried hardcoding specific IPs, but new IPs would appear. EC2 metadata detection also failed. 
Using AWS CIDR ranges or wildcards introduced security vulnerabilities.

Instead of trying to predict which IPs will make healthchecks, we instead use a custom middleware
to detect what kind of request it is, if it is a healthcheck, and if it is, we return a 200 response.

This is a commonly suggested solution to Django Applications running on AWS Elastic Beanstalk.
"""

from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin


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
        
        # Handle explicit health check paths
        if path in ["/ping/", "/health/", "/healthcheck/", "/status/"]:
            return HttpResponse("OK", content_type="text/plain", status=200)
        
        # Handle root path if it looks like a health check
        if path == "/" and request.method == "GET":
            user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
            
            # AWS ELB health check user agents
            aws_agents = ['elb-healthchecker', 'amazonelb', 'aws-elb', 'aws internal']
            if any(agent in user_agent for agent in aws_agents):
                return HttpResponse("OK", content_type="text/plain", status=200)
            
            # Simple heuristic: minimal headers and no cookies = likely health check
            header_count = len([k for k in request.META.keys() if k.startswith('HTTP_')])
            if header_count <= 3 and not request.COOKIES:
                return HttpResponse("OK", content_type="text/plain", status=200)
        
        return None  # Continue normal processing