from django.shortcuts import render


def view(request):
    context = {}
    return render(request, 'benchmarks/brain_model.html', context)
