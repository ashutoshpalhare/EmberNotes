from django.db.models import Count, Q

from .models import Note, Tag


def sidebar(request):
    """Counts and tag list for the app sidebar (signed-in users only)."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    live = Q(is_archived=False, deleted_at__isnull=True)
    counts = Note.objects.filter(user=user).aggregate(
        active=Count("pk", filter=live),
        pinned=Count("pk", filter=live & Q(is_pinned=True)),
        archive=Count("pk", filter=Q(is_archived=True, deleted_at__isnull=True)),
        trash=Count("pk", filter=Q(deleted_at__isnull=False)),
    )
    tags = (Tag.objects.filter(user=user)
            .annotate(n=Count("notes", filter=Q(notes__deleted_at__isnull=True)))
            .filter(n__gt=0))
    return {"nav_counts": counts, "nav_tags": tags}
