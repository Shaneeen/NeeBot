from __future__ import annotations

import re

from telegram import Update
from telegram.ext import ContextTypes

from .common import get_authorized_profile, safe_reply


def _assignment_has_explicit_time(assignment: dict) -> bool:
    return bool(re.search(r"\b\d{2}:\d{2}\b", assignment.get("description") or ""))


def _format_assignment_due(assignment: dict, tz, *, show_dash_when_missing_time: bool = False) -> str:
    local_due = assignment["due_at"].astimezone(tz)
    if _assignment_has_explicit_time(assignment):
        return local_due.strftime("%d %b %Y, %H:%M")
    if show_dash_when_missing_time:
        return f"{local_due.strftime('%d %b %Y')} — -"
    return local_due.strftime("%d %b %Y")


def _parse_assignment_refs(raw_text: str) -> list[str]:
    refs = [part.strip() for part in raw_text.split(",")]
    return [ref for ref in refs if ref]


async def assignment_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args).strip()
    if not text:
        await safe_reply(
            update,
            "[ assignment_ ]\n\nSave an assignment or deadline.\n\n[ formats_ ]\n↳ /assignment Title\n↳ /assignment DD-MM Title\n↳ /assignment DD Mon Title\n↳ /assignment due DD-MM Title\n\n[ examples_ ]\n↳ /assignment Submit thesis\n↳ /assignment 19-06 Submit thesis\n↳ /assignment 19 Jun Submit thesis\n↳ /assignment due 19-06 Submit thesis\n\n[ note_ ]\nAssignments without a date will be saved as unscheduled.",
        )
        return
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    assignment = context.application.bot_data["db"].add_assignment(profile["id"], text)
    due_text = (
        _format_assignment_due(
            assignment,
            context.application.bot_data["settings"].tzinfo,
        )
        if assignment["due_at"]
        else "unscheduled"
    )
    next_lines = (
        "[ next_ ]\n"
        "↳ /assignments — view active assignments\n"
        "↳ /calendar — view your monthly schedule"
        if assignment["due_at"]
        else "[ next_ ]\n"
        "↳ /assignments — view active assignments"
    )
    await safe_reply(
        update,
        "[ assignment_saved_ ]\n\n"
        f"↳ {assignment['title']}\n"
        f"due: {due_text}\n\n"
        f"{next_lines}",
    )


async def assignmentdelete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assignment_ref_text = " ".join(context.args).strip()
    if not assignment_ref_text:
        await safe_reply(
            update,
            "[ assignment_delete_ ]\n\nUse this command to delete one or more assignments.\n\n[ format_ ]\n↳ /assignmentdelete assignment_number\n↳ /assignmentdelete 1,3,4\n\n[ example_ ]\n↳ /assignmentdelete 1\n↳ /assignmentdelete 3,4,5,6\n\n[ note_ ]\n↳ Use /assignments to view your assignment numbers.",
        )
        return
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    refs = _parse_assignment_refs(assignment_ref_text)
    assignments = context.application.bot_data["db"].list_active_assignments(profile["id"])
    snapshot_by_number = {str(index): assignment for index, assignment in enumerate(assignments, start=1)}

    resolved_ids: list[str] = []
    invalid_refs: list[str] = []
    for ref in refs:
        if ref in snapshot_by_number:
            resolved_ids.append(str(snapshot_by_number[ref]["id"]))
            continue
        assignment = context.application.bot_data["db"].get_assignment(profile["id"], ref)
        if assignment:
            resolved_ids.append(str(assignment["id"]))
        else:
            invalid_refs.append(ref)

    resolved_ids = list(dict.fromkeys(resolved_ids))
    if not resolved_ids:
        await safe_reply(update, "Assignment not found. Use /assignments to view your active assignment numbers.")
        return

    deleted_assignments = []
    for assignment_id in resolved_ids:
        assignment = context.application.bot_data["db"].delete_assignment(profile["id"], assignment_id)
        if assignment:
            deleted_assignments.append(assignment)

    if not deleted_assignments:
        await safe_reply(update, "Assignment not found. Use /assignments to view your active assignment numbers.")
        return

    tz = context.application.bot_data["settings"].tzinfo
    lines = ["[ assignment_deleted_ ]", ""]
    for assignment in deleted_assignments:
        due_text = _format_assignment_due(assignment, tz) if assignment["due_at"] else "unscheduled"
        lines.append(f"↳ {assignment['title']}")
        lines.append(f"   due: {due_text}")
        lines.append("")
    if invalid_refs:
        lines.append("[ note_ ]")
        lines.append(f"↳ Skipped: {', '.join(invalid_refs)}")
        lines.append("")
    lines.append("Removed from your assignments →")
    await safe_reply(update, "\n".join(lines))


async def assignments_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    assignments = context.application.bot_data["db"].list_active_assignments(profile["id"])
    if not assignments:
        await safe_reply(
            update,
            "[ active_assignments_ ]\n\n"
            "No active assignments right now.\n\n"
            "[ next_ ]\n"
            "↳ /assignment Title\n"
            "↳ /calendar — view your monthly schedule",
        )
        return
    tz = context.application.bot_data["settings"].tzinfo
    dated: list[dict] = []
    unscheduled: list[dict] = []
    for assignment in assignments:
        if assignment["due_at"]:
            dated.append(assignment)
        else:
            unscheduled.append(assignment)

    lines = ["[ active_assignments_ ]", ""]
    item_number = 1

    if dated:
        lines.append("[ due_ ]")
        for assignment in dated:
            lines.append(f"↳ {item_number}. {assignment['title']}")
            lines.append(f"   due: {_format_assignment_due(assignment, tz)}")
            lines.append("")
            item_number += 1

    if unscheduled:
        lines.append("[ unscheduled_ ]")
        for assignment in unscheduled:
            lines.append(f"↳ {item_number}. {assignment['title']}")
            item_number += 1
        lines.append("")

    lines.extend(
        [
            "[ actions_ ]",
            "↳ /assignment Title — add assignment",
            "↳ /assignmentdelete 1 — delete assignment 1",
            "↳ /calendar — view monthly schedule",
        ]
    )
    await safe_reply(update, "\n".join(lines))
