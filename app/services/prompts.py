from collections.abc import Iterable


def render_aggregate_prompt(template: str, reviews: Iterable[str]) -> str:
    reviews_list = [r for r in reviews if r]
    formatted = "\n".join([f"- {r}" for r in reviews_list])
    if "{reviews}" in template:
        return template.replace("{reviews}", formatted)
    return template.rstrip() + "\n\nReviews:\n" + formatted
