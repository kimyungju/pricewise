"""Apply user-evidenced preference changes without rewriting other slots."""

from pricewise.regret.models import ProfilePatch, RegretProfile


def apply_patch(
    profile: RegretProfile,
    patch: ProfilePatch,
    user_message: str,
) -> RegretProfile:
    """Only the current user's words can authorize additions or reversals."""
    reset = bool(patch.reset_quote and patch.reset_quote in user_message)
    criteria = {} if reset else {item.key: item for item in profile.criteria}
    budget = None if reset else profile.budget
    for removal in patch.remove:
        if removal.source_quote in user_message:
            criteria.pop(removal.key, None)
    for item in patch.upsert:
        if item.source_quote in user_message:
            criteria[item.key] = item
    if patch.clear_budget_quote and patch.clear_budget_quote in user_message:
        budget = None
    if patch.budget and patch.budget.source_quote in user_message:
        budget = patch.budget
    return RegretProfile(criteria=list(criteria.values()), budget=budget)
