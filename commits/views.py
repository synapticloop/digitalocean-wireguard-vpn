from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from peers.views import require_admin
from peers.models import AuditLog
from .models import ConfigCommit
from .services import write_candidate, run_commit_helper


def commit_config(request):
    admin_user = require_admin(request)
    if not admin_user:
        return HttpResponseForbidden('Forbidden')
    if request.method == 'POST':
        path = write_candidate()
        result = run_commit_helper()
        status = 'success' if result.returncode == 0 else 'failed'
        commit = ConfigCommit.objects.create(actor=admin_user, status=status, summary=result.stdout[-4000:], error=result.stderr[-4000:], candidate_path=path)
        AuditLog.objects.create(actor=admin_user, action='config.commit', target_type='config_commit', target_id=str(commit.id), details={'status': status})
        messages.success(request, 'WireGuard config committed successfully.' if result.returncode == 0 else 'Commit failed; rollback was attempted.')
        return redirect('dashboard')
    return render(request, 'commits/commit.html', {'commits': ConfigCommit.objects.select_related('actor')[:20]})
