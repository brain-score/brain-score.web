import json

# all currently supported Brain-Score domains:
supported_domains = ["vision", "language"]


def domain_processor(request):

    # search for domain in request: if none found, default to vision.
    for supported_domain in supported_domains:
        if supported_domain in request.get_full_path():
            return {
                "domain": supported_domain
            }

    # by default, return vision
    return {
        "domain": "vision"
    }

# Add empty comparison_data to all template contexts by default.
# This is used to avoid errors when the comparison_data is not 
# available (due to base.html being loaded before the model.html)
def common_variables(request):
    """Add common variables to all template contexts."""
    return {
        'comparison_data': json.dumps([]),  # Default empty array
    }


def benchmark_tutorials(request):
    """
    Make benchmark tutorials available in all templates.
    Used for dynamic sidebar navigation.
    """
    from benchmarks.views.tutorials import load_benchmark_tutorials
    return {
        'benchmark_tutorials': load_benchmark_tutorials()
    }
