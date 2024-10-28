from django.shortcuts import render

from benchmarks.models import Model, BenchmarkInstance


def view(request, domain):
    models = (Model.objects
              .filter(domain=domain, public=True)
              .order_by('name')
              .values('name', 'id'))
    benchmarks = (BenchmarkInstance.objects
                  .filter(benchmark_type__domain=domain, benchmark_type__visible=True)
                  .order_by('benchmark_type__identifier', '-version')
                  .distinct('benchmark_type__identifier')
                  .values('benchmark_type__identifier', 'version'))
    context = {'domain': domain, 'models': models, 'benchmarks': benchmarks}
    return render(request, 'benchmarks/explore.html', context)
