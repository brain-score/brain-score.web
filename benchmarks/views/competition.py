from .index import get_context
from django.shortcuts import render

from ..models import CompetitionSubmission
from ..models import Submission


def view(request):
    context = get_context()
    # competition_submissions = CompetitionSubmission.objects.filter(competition='cosyne2022')
    competition_submissions = Submission.objects.filter(model_type="BrainModel")
    competition_ids = [submission.id for submission in competition_submissions]
    models = [m for m in context['models'] if m.submission_id in competition_ids]
    return render(request, 'benchmarks/competition.html', {'models': models})