"""Per-user custom group ordering helpers."""
from .models import UserGroupOrder


def _alpha(names):
    return sorted(names, key=lambda s: s.lower())


def apply_group_order(user, scope, category, group_names):
    """Return group_names reordered per the user's saved order.

    Groups not present in the saved order are appended at the end in
    case-insensitive alphabetical order. Groups in the saved order that
    no longer exist in group_names are dropped.
    """
    names = list(group_names)
    if not user or not getattr(user, 'is_authenticated', False):
        return _alpha(names)
    try:
        pref = UserGroupOrder.objects.get(user=user, scope=scope, category=category)
    except UserGroupOrder.DoesNotExist:
        return _alpha(names)

    available = set(names)
    ordered = [g for g in pref.order if g in available]
    remaining = _alpha(available - set(ordered))
    return ordered + remaining


def save_group_order(user, scope, category, ordered_groups):
    """Upsert the user's saved order for the (scope, category) pair."""
    cleaned = [str(g) for g in ordered_groups if g]
    UserGroupOrder.objects.update_or_create(
        user=user, scope=scope, category=category,
        defaults={'order': cleaned},
    )
