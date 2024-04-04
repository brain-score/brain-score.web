from django.shortcuts import render


def view(request):
    context = {}
    return render(request, 'benchmarks/release2_0.html', context)
