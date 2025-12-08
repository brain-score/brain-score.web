"""
Configuration for benchmark exclusions.

OVERVIEW:
    Benchmarks listed here are UNCHECKED by default in the leaderboard.
    They remain visible and users can re-check them to include in scoring.
    These exclusions do NOT trigger the blue "modified" column styling.

HOW TO ADD A BENCHMARK:
    1. Find the benchmark identifier:
       - Go to the leaderboard, open the filter panel
       - Inspect a checkbox (F12) - the 'value' attribute is the identifier
       - Or query: FinalBenchmarkContext.objects.filter(domain='vision')
    
    2. Add the full identifier (with version) to EXCLUDED_BENCHMARKS below
    
    3. Restart the Django server

BEHAVIOR:
    ✓ Benchmark appears in filter tree (visible)
    ✓ Checkbox is unchecked by default
    ✓ Not included in default score calculation
    ✓ Users can still check it to include it
    ✓ No blue "modified" column styling
    ✓ Shows info icon (ⓘ) with tooltip explaining exclusion
"""

# Benchmarks to exclude by default (unchecked but visible)
# Format: list of full benchmark identifiers (with version suffix)
EXCLUDED_BENCHMARKS = [

    # Coggan to possibly be excluded in future:
    # "tong.Coggan2024_fMRI.V1-rdm_v1",
    # "tong.Coggan2024_fMRI.V2-rdm_v1",
    # "tong.Coggan2024_fMRI.V4-rdm_v1",
    # "tong.Coggan2024_fMRI.IT-rdm_v1",
    # "tong.Coggan2024_behavior-ConditionWiseAccuracySimilarity_v1"
]

# Domain-specific exclusions (if needed in the future)
EXCLUDED_BENCHMARKS_BY_DOMAIN = {
    'vision': [
        # Vision-specific exclusions
    ],
    'language': [
        # Language-specific exclusions
    ]
}


def get_excluded_benchmarks(domain='vision'):
    """
    Get the list of excluded benchmarks for a given domain.
    
    Args:
        domain (str): The domain ('vision' or 'language')
        
    Returns:
        list: List of benchmark identifiers to exclude by default
    """
    # Combine global exclusions with domain-specific ones
    excluded = set(EXCLUDED_BENCHMARKS)
    excluded.update(EXCLUDED_BENCHMARKS_BY_DOMAIN.get(domain, []))
    return list(excluded)
