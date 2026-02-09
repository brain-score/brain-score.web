from django.shortcuts import render

from benchmarks.models import Model, BenchmarkInstance


def view(request, domain):
    base_query = Model.objects.filter(domain=domain, public=True)

    representative_groups = [Model.Group.REFERENCE, Model.Group.TOP10_2024, Model.Group.BASE]

    representative_models = (base_query
                             .filter(group__in=representative_groups)
                             .order_by('name')
                             .values('name', 'id'))

    other_models = (base_query
                    .filter(group__isnull=True)
                    .order_by('name')
                    .values('name', 'id'))

    total_model_count = base_query.count()

    benchmarks = (BenchmarkInstance.objects
                  .filter(benchmark_type__domain=domain, benchmark_type__visible=True)
                  .order_by('benchmark_type__identifier', '-version')
                  .distinct('benchmark_type__identifier')
                  .values('id', 'benchmark_type__identifier', 'version'))

    context = {
        'domain': domain,
        'representative_models': representative_models,
        'other_models': other_models,
        'total_model_count': total_model_count,
        'benchmarks': benchmarks,
    }
    return render(request, 'benchmarks/explore.html', context)
