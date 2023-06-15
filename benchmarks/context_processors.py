
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
