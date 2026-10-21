"""PawPal+ core system: class skeletons based on diagrams/uml.mmd.

An Owner has Pets; each Pet has care Tasks. The Scheduler builds a
DailyPlan from those tasks using time constraints, priority, and preferences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from enum import Enum
from typing import Optional


class Priority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


@dataclass
class TimeConstraint:
    earliest_start: time
    latest_end: time
    is_fixed: bool = False

    def fits(self, start: time, duration_minutes: int) -> bool:
        """Return True if a task starting at `start` and lasting `duration_minutes` fits this window."""
        pass


@dataclass
class Task:
    title: str
    duration_minutes: int
    priority: Priority = Priority.MEDIUM
    time_constraint: Optional[TimeConstraint] = None
    preference: str = ""
    completed: bool = False

    def mark_complete(self) -> None:
        """Mark this task as completed."""
        pass

    def has_time_constraint(self) -> bool:
        """Return True if this task has a time constraint."""
        pass

    def priority_score(self) -> int:
        """Return a numeric score used for sorting tasks by importance."""
        pass


@dataclass
class Pet:
    name: str
    species: str
    age: int
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a care task for this pet."""
        pass

    def remove_task(self, task_title: str) -> None:
        """Remove the task with the given title."""
        pass

    def get_tasks(self) -> list[Task]:
        """Return all tasks for this pet."""
        pass


@dataclass
class Preference:
    description: str
    preferred_time_of_day: str  # e.g. "morning", "afternoon", "evening"
    weight: int = 1

    def applies_to(self, task: Task) -> bool:
        """Return True if this preference is relevant to the given task."""
        pass


@dataclass
class Owner:
    name: str
    available_minutes: int
    day_start: time
    day_end: time
    pets: list[Pet] = field(default_factory=list)
    preferences: list[Preference] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner."""
        pass

    def remove_pet(self, pet_name: str) -> None:
        """Remove the pet with the given name."""
        pass

    def get_pet(self, pet_name: str) -> Optional[Pet]:
        """Return the pet with the given name, or None if not found."""
        pass

    def add_preference(self, pref: Preference) -> None:
        """Add a scheduling preference."""
        pass

    def get_all_tasks(self) -> list[Task]:
        """Return every task across all of this owner's pets."""
        pass


@dataclass
class ScheduledTask:
    task: Task
    pet: Pet
    start_time: time
    end_time: time
    reason: str = ""

    def overlaps(self, other: ScheduledTask) -> bool:
        """Return True if this scheduled task's time range overlaps another's."""
        pass


@dataclass
class DailyPlan:
    date: date
    items: list[ScheduledTask] = field(default_factory=list)
    skipped_tasks: list[Task] = field(default_factory=list)

    def add_item(self, item: ScheduledTask) -> None:
        """Add a scheduled task to the plan."""
        pass

    def total_minutes(self) -> int:
        """Return the total scheduled minutes in the plan."""
        pass

    def view_tasks(self) -> list[ScheduledTask]:
        """Return the scheduled tasks, ordered by start time."""
        pass

    def explain(self) -> str:
        """Return a human-readable explanation of why the plan looks the way it does."""
        pass


class Scheduler:
    def __init__(self, owner: Owner) -> None:
        self.owner = owner

    def generate_plan(self) -> DailyPlan:
        """Build a DailyPlan from the owner's pets, tasks, and preferences."""
        pass

    def sort_tasks(self, tasks: list[Task]) -> list[Task]:
        """Return tasks ordered by priority and constraints."""
        pass

    def filter_tasks(self, tasks: list[Task]) -> list[Task]:
        """Return only the tasks that should be considered (e.g. not completed)."""
        pass

    def find_slot(self, task: Task, plan: DailyPlan) -> Optional[time]:
        """Return the earliest valid start time for a task in the plan, or None if none fits."""
        pass

    def detect_conflicts(self, plan: DailyPlan) -> list[str]:
        """Return descriptions of any overlapping tasks in the plan."""
        pass
