from django.shortcuts import render


def view(request):
    context = {}
    return render(request, 'benchmarks/competition2024.html', context)
