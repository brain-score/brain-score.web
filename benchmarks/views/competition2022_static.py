from django.shortcuts import render


def view(request):
    """
    Static view for the 2022 Brain-Score Competition page.
    This serves a static version of the competition page without dynamic data.
    """
    context = {
        'page_title': '2022 Brain-Score Competition',
        'meta_description': 'The 2022 Brain-Score Competition - evaluating computational models of primate vision.'
    }
    return render(request, 'benchmarks/competition2022_static.html', context)
