import json
import logging
from typing import Union, List, Dict, Any, Tuple
from django.contrib.auth.models import User
from django.utils.functional import wraps
from django.db.models import Q
from django.core.cache import cache
import numpy as np
import pandas as pd
from colour import Color
from django.shortcuts import render
from django.template.defaulttags import register
from django.views.decorators.cache import cache_page
from time import time
from benchmarks.models import Score, FinalBenchmarkContext, FinalModelContext, Reference, FlattenedModelContext, BenchmarkMinMax
from ..utils import cache_get_context, get_benchmark_exclusion_list, apply_exclusion_patterns, rebuild_model_tree, recompute_upstream_scores, update_benchmark_children_count

_logger = logging.getLogger(__name__)

BASE_DEPTH = 1
ENGINEERING_ROOT = 'engineering'

'''
Reference for previous color scheme
Used for benchmark cards
'''
colors_redgreen = list(Color('red').range_to(Color('#1BA74D'), 101))
colors_gray = list(Color('#f2f2f2').range_to(Color('#404040'), 101))
# scale colors: highlight differences at the top-end of the spectrum more than at the lower end
a, b = 0.2270617, 1.321928  # fit to (0, 0), (60, 50), (100, 100)
colors_redgreen = [colors_redgreen[int(a * np.power(i, b))] for i in range(len(colors_redgreen))]
colors_gray = [colors_gray[int(a * np.power(i, b))] for i in range(len(colors_gray))]
color_suffix = '_color'
color_None = '#e0e1e2'

#@cache_base_model_query(timeout=1 * 15 * 60)  # 15 minutes cache
# Explore caching entire leaderboard context without any filtering
# which is then used downstream. Unclear if this has performance benefits.
def get_base_model_query(domain="vision"):
    """Get the base model query for a domain before any filtering"""
    return FinalModelContext.objects.filter(domain=domain)  # Return QuerySet instead of list


# Cache the leaderboard HTML page for 15 minutes at a time
# Server-side HTML caching until leaderboard views are introduced.
# Consider using client-side caching in the future
#@cache_page(1 * 15 * 60)
def view(request, domain: str):
    # Get the authenticated user if any
    user = request.user if request.user.is_authenticated else None

    benchmark_filter = lambda benchmarks: apply_exclusion_patterns(benchmarks, get_benchmark_exclusion_list(["Coggan*", "engineering_vision"], domain="vision"))

    # Get the appropriate context based on user authentication
    start_time = time()
    if user:
        # User is authenticated - get personalized context (used for profile views)
        leaderboard_context = get_context(user=user, domain=domain, show_public=False)
    else:
        # No user - get public context
        leaderboard_context = get_context(domain=domain, show_public=True)#, benchmark_filter=benchmark_filter)
    end_time = time()
    print(f"Total time taken to get leaderboard context: {end_time - start_time} seconds")
   
    return render(request, 'benchmarks/leaderboard/leaderboard.html', leaderboard_context)

# Maintain 24-hr cache for leaderboard view
@cache_get_context(timeout=24 * 60 * 60)
def get_context(user=None, domain="vision", benchmark_filter=None, model_filter=None, show_public=False):
    # ------------------------------------------------------------------
    # 1) QUERY MATERIALIZED VIEWS
    # ------------------------------------------------------------------ 
    if benchmark_filter:
        benchmarks = list(benchmark_filter(FinalBenchmarkContext.objects.filter(domain=domain, visible=True)).order_by('overall_order'))
        benchmarks = update_benchmark_children_count(benchmarks)
        all_model_data = benchmark_filter(FlattenedModelContext.objects.filter(model_domain=domain, model_public=True))
        models = recompute_upstream_scores(all_model_data)
        models = rebuild_model_tree(models)
    else:
        # If user is superuser, show all benchmarks, otherwise only show visible ones
        if user and user.is_superuser:
            benchmarks = list(FinalBenchmarkContext.objects.filter(domain=domain).order_by('overall_order'))
        else:
            benchmarks = list(FinalBenchmarkContext.objects.filter(domain=domain, visible=True).order_by('overall_order'))

        # Build model query based on user permissions
        # Necessary to wrap query in function to allow caching of query results. 
        # For now, it is disabled. Provided minimal performance gains.
        start_time = time()
        all_model_data = get_base_model_query(domain)
        end_time = time()
        print(f"Total time taken to get base model query: {end_time - start_time} seconds")

        start_time = time()
        if user is None:
            # Public view - only show public models
            models = all_model_data.filter(public=True)
        elif user.is_superuser:
            # Superuser sees everything (super user profile view)
            models = all_model_data
        else:
            # Filter for user's models (user profile view)
            models = all_model_data.filter(Q(user__id=user.id))

        end_time = time()
        print(f"Total time taken to filter models: {end_time - start_time} seconds")

    # Convert to list only when needed for ranking and further processing
    start_time = time()
    models = list(models)
    end_time = time()
    print(f"Total time taken to convert models to list: {end_time - start_time} seconds")

    # Apply any additional model filters
    if model_filter:
        model_query = list(model_filter(models))

    # Recalculate ranks based on the filtered set of models
    # Necessary for various model-variant views (e.g., user profile view vs public vs super user profile view which have different sets of models)
    start_time = time()
    model_rows_reranked = filter_and_rank_models(models, domain)
    end_time = time()
    print(f"Total time taken to filter and rank models: {end_time - start_time} seconds")

    # ------------------------------------------------------------------
    # 2) BUILD OTHER CONTEXT ITEMS AS NEEDED
    # Materialized views for some of these exist, but simple list comprehension was fast enough.
    # If model list grows, consider using the materialized views.
    # ------------------------------------------------------------------ 
    # Identify leaf benchmarks (actual runnable benchmarks and not parents)
    start_time = time()
    benchmark_names = [b.identifier for b in benchmarks if b.number_of_all_children == 0]
    # Identify parents and map children to parents
    benchmark_parents = {
        bench.identifier: (f"{bench.parent['identifier']}_v0" if bench.parent and 'identifier' in bench.parent else None)
        for bench in benchmarks
    }   
    # Identify uniform parents (parents that are the same for all children)
    uniform_parents = set(benchmark_parents.values())
    # Identify benchmarks that should not be shown (depth > BASE_DEPTH or engineering root in root_parent)
    # Controls which benchmarks are visible in the leaderboard table based on depth and type (i.e., vision vs engineering)
    not_shown_set = {
        bench.identifier for bench in benchmarks
        if bench.depth > BASE_DEPTH
        or (ENGINEERING_ROOT not in bench.identifier
            and ENGINEERING_ROOT in bench.root_parent)
    }
    finish_time = time()
    print(f"Total time taken to identify benchmarks that should not be shown: {finish_time - start_time} seconds")
    
    # Add submittable benchmarks for authenticated users
    start_time = time()
    submittable_benchmarks = _collect_submittable_benchmarks(benchmarks=benchmarks, user=user) if user else None
    end_time = time()
    print(f"Total time taken to collect submittable benchmarks: {end_time - start_time} seconds")
    
    # Build CSV data and comparison data
    # Combined to a single pass through models to avoid redundant calculations.
    start_time = time()
    csv_data, comparison_data = _build_model_data(benchmarks, model_rows_reranked)
    end_time = time()
    print(f"Total time taken to build model data: {end_time - start_time} seconds")
    
    # ------------------------------------------------------------------
    # 3) PREPARE FINAL CONTEXT
    # ------------------------------------------------------------------ 
    context = {
        'domain': domain,
        'models': model_rows_reranked,
        'benchmarks': benchmarks,
        'benchmark_names': benchmark_names,
        'submittable_benchmarks': submittable_benchmarks,
        'benchmark_parents': benchmark_parents,
        'uniform_parents': uniform_parents,
        'not_shown_set': not_shown_set,
        'BASE_DEPTH': BASE_DEPTH,
        'has_user': user is not None,
        'comparison_data': json.dumps(comparison_data),
        'citation_general_url': 'https://www.cell.com/neuron/fulltext/S0896-6273(20)30605-X',
        'citation_general_title': 'Integrative Benchmarking to Advance Neurally Mechanistic Models of Human Intelligence',
        'citation_general_bibtex': (
            '@article{Schrimpf2020integrative,\n'
            '  title={Integrative Benchmarking to Advance Neurally Mechanistic Models of Human Intelligence},\n'
            '  author={Schrimpf, Martin and Kubilius, Jonas and Lee, Michael J and Murty, N Apurva Ratan and '
            'Ajemian, Robert and DiCarlo, James J},\n'
            '  journal={Neuron},\n'
            '  year={2020},\n'
            '  url={https://www.cell.com/neuron/fulltext/S0896-6273(20)30605-X}\n'
            '}'
        ),
    }
    
    # Add domain-specific citation information
    if domain == "vision":
        context.update({
            'citation_domain_url': 'https://www.biorxiv.org/content/early/2018/09/05/407007',
            'citation_domain_title': 'Brain-Score: Which Artificial Neural Network for Object Recognition is most Brain-Like?',
            'citation_domain_bibtex': ("@article{SchrimpfKubilius2018BrainScore,\n"
                                  "  title={Brain-Score: Which Artificial Neural Network for Object Recognition is most Brain-Like?},\n"
                                  "  author={Martin Schrimpf and Jonas Kubilius and Ha Hong and Najib J. Majaj and "
                                  "Rishi Rajalingham and Elias B. Issa and Kohitij Kar and Pouya Bashivan and Jonathan "
                                  "Prescott-Roy and Franziska Geiger and Kailyn Schmidt and Daniel L. K. Yamins and James J. DiCarlo},\n"
                                  "  journal={bioRxiv preprint},\n"
                                  "  year={2018},\n"
                                  "  url={https://www.biorxiv.org/content/10.1101/407007v2}\n"
                                  "}")
        })
    elif domain == "language":
        context.update({
            'citation_domain_url': 'https://www.pnas.org/content/118/45/e2105646118',
            'citation_domain_title': "The neural architecture of language: Integrative modeling converges on predictive processing",
            'citation_domain_bibtex': ("@article{schrimpf2021neural,\n"
                                  "  title={The neural architecture of language: Integrative modeling converges on predictive processing},\n"
                                  "  author={Schrimpf, Martin and Blank, Idan Asher and Tuckute, Greta and Kauf, Carina and "
                                  "Hosseini, Eghbal A and Kanwisher, Nancy and Tenenbaum, Joshua B and Fedorenko, Evelina},\n"
                                  "  journal={Proceedings of the National Academy of Sciences},\n"
                                  "  volume={118},\n"
                                  "  number={45},\n"
                                  "  pages={e2105646118},\n"
                                  "  year={2021}\n"
                                  "}")
        })
    else:
        context.update({
            'citation_domain_url': '',
            'citation_domain_title': '',
            'citation_domain_bibtex': ''
        })
    
    context['csv_downloadable'] = csv_data
    return context


def filter_and_rank_models(models, domain: str = "vision"):
    """
    Filters out models without a valid average_{domain} score (must be a number or "X") and recalculates ranks.
    Returns a list of models with updated ranks.
    """
    if not isinstance(models, list):
        models = list(models)

    model_scores = []
    for model in models:
        if get_value(model, "scores") is not None:
            for score in get_value(model, "scores"):
                benchmark_id = get_value(score, "benchmark", {}).get("benchmark_type_id")
                if benchmark_id == f"average_{domain}":
                    val = get_value(score, "score_ceiled", get_value(score, "score_ceiled"))
                    if val is None or val == "":
                        # Exclude models with None or empty string
                        break
                    if val == "X":
                        # "X" is valid, but always ranked at the bottom
                        model_scores.append((model, None, True))
                        break
                    try:
                        val_float = float(val)
                        model_scores.append((model, val_float, False))
                    except Exception:
                        # Exclude models with non-numeric, non-"X" values
                        break
                    break

    # Sort: valid numbers (descending), then "X" at the bottom (tied), exclude None/null
    model_scores.sort(
        key=lambda x: (
            1 if x[2] else 0,  # is_x: False (0) comes before True (1)
            -(x[1] if x[1] is not None else 0),  # valid numbers descending, "X" as 0
            get_value(x[0], "name", str(get_value(x[0], "model_id", "")))  # tiebreaker
        )
    )

    # Assign ranks: valid numbers get ranks, all "X" get the same (last) rank
    rank_map = {}
    current_rank = 1
    previous_score = None
    tied_count = 0
    
    for i, (model, score, is_x) in enumerate(model_scores):
        if is_x:
            # All "X" get the same rank (after all valids)
            break
            
        if i == 0 or score != previous_score:
            # If we had a tie, increment rank by the number of tied models
            if tied_count > 0:
                current_rank += tied_count
            tied_count = 1
            rank_map[get_value(model, "model_id")] = current_rank
        else:
            # This is a tie, use the same rank as the previous model
            tied_count += 1
            prev_model = model_scores[i-1][0]
            rank_map[get_value(model, "model_id")] = rank_map[get_value(prev_model, "model_id")]
            
        previous_score = score

    # Assign the same rank to all "X" (after all valids)
    x_rank = current_rank + tied_count
    for model, score, is_x in model_scores:
        if is_x:
            set_value(model, "rank", x_rank)
        else:
            set_value(model, "rank", rank_map[get_value(model, "model_id")])

    # Return all models, sorted by rank
    ranked_models = [model for model, _, _ in model_scores]
    ranked_models.sort(key=lambda model: get_value(model, "rank"))
    return ranked_models



def _build_model_data(benchmarks: List[FinalBenchmarkContext], 
                      models: List[FinalModelContext]
                      ) -> Tuple[Union[str, pd.DataFrame], List[Dict[str, Any]]]:
    """
    Build both comparison data and scores dataframe in a single pass through models.
    Returns: (csv_data, comparison_data) tuple
    comparison_data: Build an array object for use by the JavaScript frontend to dynamically compare trends across benchmarks.
        ```
        [
            {"dicarlo.Rajalingham2018-i2n_v2-score": .521,
             "dicarlo.Rajalingham2018-i2n_v2-error": 0.00391920504344273,
             "behavior_v0-score": ".521",
             ...,
             "model": "mobilenet_v2_1.0_224",
            },
            ...
        ]
        ```
    csv_data: Build a dataframe of model scores for download as CSV.
    """
    # Pre-compute benchmark names set
    benchmark_names = {benchmark.benchmark_type_id for benchmark in benchmarks}
    
    # Initialize lists of dictionaries to store data
    records = []  # For CSV download
    comparison_data = []  # For comparison page
    
    # Single pass through models
    for model in models:
        # Initialize both data structures for this model
        record = {
            "model_name": get_value(model, "name"),
            "layers": json.dumps(get_value(model, "layers")) if get_value(model, "layers") else ""  # Add layer map information to CSV download as a column
        }
        model_data = {
            "model": get_value(model, "name")
        }
        
        # Process all scores for this model
        if get_value(model, "scores") is not None:
            for score in get_value(model, "scores"):
                benchmark_id = score["benchmark"]["benchmark_type_id"]
                versioned_benchmark_id = score["versioned_benchmark_identifier"]
                # Add to scores dataframe if it's a relevant benchmark
                if benchmark_id in benchmark_names:
                    record[benchmark_id] = score["score_ceiled"]
            
                model_data.update({
                    f"{versioned_benchmark_id}-score": score['score_ceiled'],
                    f"{versioned_benchmark_id}-error": score['error'],
                    f"{versioned_benchmark_id}-is_complete": score['is_complete']
                })
        
            # Add to both result sets
            records.append(record)
            comparison_data.append(model_data)
    
    # Create DataFrame and convert to CSV
    csv_data = "No models submitted yet."
    if records:
        df = pd.DataFrame.from_records(records)
        df.set_index('model_name', inplace=True)
        csv_data = df.to_csv(index=True)
    
    return csv_data, comparison_data

# Resubmissions are currently not supported. Retaining for future use.
def _collect_submittable_benchmarks(benchmarks: List[FinalBenchmarkContext], user: User) -> Dict:
    """
    gather benchmarks that:
    - any of a user's models have been evaluated on, if user is not a superuser
    - all benchmarks, if user is a superuser
    """

    benchmark_types = {benchmark.identifier: benchmark.benchmark_type_id
                       for benchmark in benchmarks if not hasattr(benchmark, 'children')}
    # the above dictionary creation will already deal with duplicates from benchmarks with multiple versions
    if user.is_superuser:  # superusers can resubmit on all available benchmarks
        return benchmark_types

    previously_evaluated_benchmarks = [benchmark_type_id
                                       for benchmark_type_id in Score.objects
                                       .select_related('benchmark')
                                       .filter(model__owner=user)
                                       .distinct('benchmark__benchmark_type_id')
                                       .values_list('benchmark__benchmark_type_id', flat=True)]
    benchmark_selection = {identifier: benchmark_type_id for identifier, benchmark_type_id in benchmark_types.items()
                           if benchmark_type_id in previously_evaluated_benchmarks}
    return benchmark_selection


def get_value(item, key, default=None):
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)

def set_value(item, key, value):
    if isinstance(item, dict):
        item[key] = value
    else:
        setattr(item, key, value)

# Preserving the original color scheme for now. No longer used as color is determined in database materialized view.
# May need the following four functions for custom views.
def represent(value):
    if isinstance(value, (int, float)):  # None in sqlite, nan in postgres
        return "{:.3f}".format(value).lstrip('0') if value < 1 else "{:.1f}".format(value)
    if value is None:
        return ""
    elif value == "NaN":
        return "X"

def get_visibility(model, user):
    """
    Determine the visibility level of a model based on the user's permissions.
    Returns: 'private_owner', 'private_not_owner', or 'public'
    """
    # Handles private competition models:
    if (not get_value(model, "public")) and (get_value(model, "competition") is not None):
        # Model is a private competition model, and user is logged in (or superuser)
        if (user is not None) and (user.is_superuser or 
                                  (isinstance(model.user, dict) and model.user.get('id') == user.id) or
                                  (hasattr(model.user, 'id') and model.user.id == user.id)):
            return "private_owner"
        # Model is a private competition model, and user is NOT logged in (or NOT superuser)
        else:
            return "private_not_owner"
    # Model is public
    else:
        return "public"

# Used in benchmark.py view to generate a string identifier for a reference
# benchmark.py has not been updated to leverage materialized view as it was fast already.
def reference_identifier(reference: Reference) -> Union[str, None]:
    return f"{reference.author} et al., {reference.year}" if reference else None

# Adds python functions so the HTML can retrieve dictionary items
@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


# Used to determine whether a column should be visible to begin with
@register.filter
def in_set(hidden_set, key):
    if key in hidden_set:
        return "none"
    else:
        return ""


# Same as above, but used for headers, because their names are different than the cells.
@register.filter
def in_set_hidden(hidden_set, key):
    if hidden_set[key] in hidden_set:
        return "none"
    else:
        return ""


# Allows children to have defining symbols before their names
@register.filter
def get_initial_characters(dictionary, key):
    number_of_characters = -1
    checking_key = key
    while checking_key in dictionary:
        checking_key = dictionary[checking_key]
        number_of_characters += 1

    return "–" * number_of_characters


# Checks if the parent's name or the part of the parent's name after the first period are in the given dictionary.
@register.filter
def get_parent_item(dictionary, key):
    # Handle case where dictionary is actually a string
    if isinstance(dictionary, str):
        return None
    # Use .get() to avoid KeyError for dictionaries
    return_value = dictionary.get(key, "")
    if not return_value:
        return None
    # Optionally, process the string if you want to strip a lab prefix.
    if "." in return_value:
        parts = return_value.split('.')
        # For example, if you want to return everything after the first dot:
        return ".".join(parts[1:])
    else:
        return return_value

@register.filter
def format_score(score):
    try:
        return f"{score:.3f}"
    except:  # e.g. 'X'
        return score


@register.filter
def display_model(model, user):
    visibility = get_visibility(model, user)
    if visibility == "private_owner":
        return get_value(model, "name")
    elif visibility == "private_not_owner":
        return f"Model #{get_value(model, 'id')}"
    else:
        return get_value(model, "name")


# controls the way model submitter appears (name vs Anonymous Submitter) in table
@register.filter
def display_submitter(model, user):
    visibility = get_visibility(model, user)
    model_user = get_value(model, "user")
    if visibility == "private_owner":
        if isinstance(model_user, dict):
            return model_user.get("display_name", "")
        else:
            return getattr(model_user, "display_name", "")
    elif visibility == "private_not_owner":
        if isinstance(model_user, dict):
            return f"Anonymous Submitter #{model_user.get('id', '')}"
        else:
            return f"Anonymous Submitter #{getattr(model_user, 'id', '')}"
    else:
        if isinstance(model_user, dict):
            return model_user.get("display_name", "")
        else:
            return getattr(model_user, "display_name", "")


# controls how the benchmark roots are displayed in the comparison graphs
@register.filter
def simplify_domain(benchmark_name: str) -> str:
    suffixed_benchmarks = ['average', 'engineering', "neural", "behavior"]
    for suffixed_name in suffixed_benchmarks:
        if benchmark_name.startswith(f"{suffixed_name}_"):
            return suffixed_name
    return benchmark_name
