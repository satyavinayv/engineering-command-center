"""
AI context builder (spec section 31 - "AI Privacy Layer"). This is the
single most important file for the "AI should not go through every
email" requirement: the AI provider NEVER sees raw email bodies, full
Jira issue text, GitLab diffs, or any database dump. It sees exactly
this - a capped, already-prioritized list of one-line titles, sources,
and priorities that the deterministic Action Engine already computed.

Cap at 30 items, hard limit, regardless of how many action items exist
- both to keep prompts small/fast/cheap and because a briefing that
tries to mention 200 items isn't useful anyway; the P0/P1 sort order
means the most important items are always the ones included.
"""
MAX_ITEMS_IN_PROMPT = 30


def build_daily_briefing_prompt(action_items: list[dict]) -> str:
    capped = action_items[:MAX_ITEMS_IN_PROMPT]

    counts: dict[str, int] = {}
    for item in action_items:
        counts[item["priority"]] = counts.get(item["priority"], 0) + 1
    counts_line = ", ".join(f"{v} {k}" for k, v in sorted(counts.items()))

    lines = [f"- [{item['priority']}] ({item['source']}) {item['title']}" for item in capped]

    return (
        "You are an engineering assistant writing a short morning briefing "
        "for one software test engineer. Below is their prioritized list "
        "of action items (P0 = critical, P1 = today, P2 = this week). "
        "Write 3-5 plain-prose sentences: what's most urgent, what can "
        "wait, and one clear suggestion for what to tackle first. Do not "
        "invent details that aren't in the list below, and do not repeat "
        "the raw list back verbatim.\n\n"
        f"Counts: {counts_line or 'nothing pending'}\n\n"
        "Items:\n" + ("\n".join(lines) if lines else "(none)")
    )