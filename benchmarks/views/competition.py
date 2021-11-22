from .index import get_context
from django.shortcuts import render

# from ..models import CompetitionSubmission
from ..models import Submission


def view(request):
    context = get_context()

    # change to commented out line once fixtures are put into place
    # context['models'] = [model for model in context['models'] if model.competition == 'cosyne2022']
    context['models'] = [model for model in context['models'] if model.submission_id >= 100]
    return render(request, 'benchmarks/competition.html', context)
