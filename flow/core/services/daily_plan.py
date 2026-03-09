"""Daily plan service operations."""

from __future__ import annotations

from datetime import date, datetime
from typing import TypedDict

from flow.database.sqlite import DailyPlanEntryInput, SqliteDB
from flow.models import Item
from flow.utils.llm import complete


class DailyWorkspaceCandidates(TypedDict):
    must_address: list[Item]
    inbox: list[Item]
    ready_actions: list[Item]
    suggested: list[Item]


class DailyWorkspaceState(TypedDict):
    needs_plan: bool
    top_items: list[Item]
    bonus_items: list[Item]
    candidates: DailyWorkspaceCandidates


class DailyWrapSummary(TypedDict):
    top_total: int
    top_completed: int
    bonus_total: int
    bonus_completed: int
    all_top_completed: bool
    headline: str
    coaching_feedback: str
    completed_top_items: list[dict[str, str]]
    completed_bonus_items: list[dict[str, str]]
    open_planned_items: list[dict[str, str]]


class DailyPlanService:
    """Encapsulates persistence and read-model logic for today's plan."""

    def __init__(self, db: SqliteDB) -> None:
        self._db = db

    def save_plan(
        self, plan_date: str, top_item_ids: list[str], bonus_item_ids: list[str]
    ) -> None:
        entries: list[DailyPlanEntryInput] = []
        for index, item_id in enumerate(top_item_ids, start=1):
            entries.append({"item_id": item_id, "bucket": "top", "position": index})
        for index, item_id in enumerate(bonus_item_ids, start=1):
            entries.append({"item_id": item_id, "bucket": "bonus", "position": index})
        self._db.replace_daily_plan(plan_date, entries)

    def get_plan_items(self, plan_date: str) -> tuple[list[Item], list[Item]]:
        top_items: list[Item] = []
        bonus_items: list[Item] = []
        for entry in self._db.list_daily_plan(plan_date):
            if entry["item"].status != "active":
                continue
            if entry["bucket"] == "top":
                top_items.append(entry["item"])
            else:
                bonus_items.append(entry["item"])
        return top_items, bonus_items

    def get_wrap_summary(self, plan_date: str) -> DailyWrapSummary:
        entries = self._db.list_daily_plan(plan_date)
        summary = self._db.get_daily_plan_summary(plan_date)
        completed_top_items: list[dict[str, str]] = []
        completed_bonus_items: list[dict[str, str]] = []
        open_planned_items: list[dict[str, str]] = []

        for entry in entries:
            item_summary = {"id": entry["item"].id, "title": entry["item"].title}
            if entry["item"].status == "done":
                if entry["bucket"] == "top":
                    completed_top_items.append(item_summary)
                else:
                    completed_bonus_items.append(item_summary)
            else:
                open_planned_items.append(item_summary)

        headline, coaching_feedback = self._evaluate_wrap(
            top_total=summary["top_total"],
            top_completed=summary["top_completed"],
            bonus_total=summary["bonus_total"],
            bonus_completed=summary["bonus_completed"],
        )
        return {
            **summary,
            "all_top_completed": summary["top_total"] > 0
            and summary["top_total"] == summary["top_completed"],
            "headline": headline,
            "coaching_feedback": coaching_feedback,
            "completed_top_items": completed_top_items,
            "completed_bonus_items": completed_bonus_items,
            "open_planned_items": open_planned_items,
        }

    def generate_wrap_insight(self, plan_date: str) -> str | None:
        """Generate a short AI wrap insight from today's structured summary."""
        summary = self.get_wrap_summary(plan_date)
        prompt = (
            "You are summarizing one workday for a GTD app user.\n"
            "Write one concise insight sentence. Stay factual, grounded, and non-judgmental.\n"
            f"Plan date: {plan_date}\n"
            f"Top completed: {summary['top_completed']}/{summary['top_total']}\n"
            f"Bonus completed: {summary['bonus_completed']}/{summary['bonus_total']}\n"
            f"Completed Top items: {[item['title'] for item in summary['completed_top_items']]}\n"
            f"Completed Bonus items: {[item['title'] for item in summary['completed_bonus_items']]}\n"
            f"Open planned items: {[item['title'] for item in summary['open_planned_items']]}\n"
            f"Deterministic headline: {summary['headline']}\n"
            f"Deterministic coaching: {summary['coaching_feedback']}\n"
        )
        result = complete(prompt)
        if result is None:
            return None
        return result.strip() or None

    @staticmethod
    def _evaluate_wrap(
        *,
        top_total: int,
        top_completed: int,
        bonus_total: int,
        bonus_completed: int,
    ) -> tuple[str, str]:
        if top_total > 0 and top_completed == top_total and bonus_total <= 2:
            return (
                "Strong day",
                "You protected the full Top 3 and kept the plan realistic.",
            )
        if top_total > 0 and top_completed == top_total:
            return (
                "Solid day",
                "You finished the full Top 3 even with extra Bonus load.",
            )
        if top_total >= 3 and top_completed <= 1 and bonus_total >= 3:
            return (
                "Plan was too ambitious",
                "Too much Bonus work diluted the day. Tighten the Top 3 and reduce bonus load next time.",
            )
        if top_completed > 0:
            return (
                "Solid day",
                "You landed some committed work. Narrow the plan slightly to finish more of the Top 3.",
            )
        return (
            "Reset tomorrow",
            "The plan did not convert into completed priority work. Start with a smaller Top 3 tomorrow.",
        )

    @staticmethod
    def is_due_on_or_before(item: Item, plan_day: date) -> bool:
        """Return True when an item has a due date on or before the plan day."""
        if item.due_date is None:
            return False
        try:
            return item.due_date.date() <= plan_day
        except (AttributeError, TypeError):
            return False
