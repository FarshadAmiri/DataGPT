"""
Indexing progress tracking view
"""
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required


@login_required(login_url='users:login')
def indexing_progress_view(request):
    """
    Return current indexing progress for AJAX polling
    """
    progress = request.session.get('indexing_progress')
    if not progress:
        return JsonResponse({
            'current': 0,
            'total': 0,
            'filename': ''
        })
    
    return JsonResponse({
        'current': progress.get('current', 0),
        'total': progress.get('total', 0),
        'filename': progress.get('filename', '')
    })
