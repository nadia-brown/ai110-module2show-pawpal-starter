"""PawPal+ core system, based on diagrams/uml.mmd.

An Owner has Pets; each Pet has care Tasks. The Scheduler builds a
DailyPlan from those tasks using time constraints, priority, and preferences.

Times are stored as datetime.time for readability, but all scheduling math is
done in "minutes since midnight" (plain ints), since datetime.time does not
support arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, time, timedelta
from enum import Enum
from itertools import accumulate
from typing import Any, Callable, Optional


# --- Time helpers ---------------------------------------------------------

def to_minutes(t: time) -> int:
    """Convert a time to minutes since midnight."""
    return t.hour * 60 + t.minute


def from_minutes(minutes: int) -> time:
    """Convert minutes since midnight back to a time (clamped to 23:59)."""
    minutes = max(0, min(minutes, 23 * 60 + 59))
    return time(minutes // 60, minutes % 60)


def format_time(t: time) -> str:
    """Format a time as HH:MM."""
    return t.strftime("%H:%M")


# Windows used by Preference.preferred_time_of_day, as (start, end) minutes.
TIME_OF_DAY_WINDOWS: dict[str, tuple[int, int]] = {
    "morning": (6 * 60, 12 * 60),
    "afternoon": (12 * 60, 17 * 60),
    "evening": (17 * 60, 22 * 60),
}


# --- Model ----------------------------------------------------------------

class Priority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class TaskCategory(Enum):
    WALK = "walk"
    FEEDING = "feeding"
    MEDS = "meds"
    GROOMING = "grooming"
    ENRICHMENT = "enrichment"
    OTHER = "other"


class Frequency(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class TimeConstraint:
    earliest_start: time
    latest_end: time
    is_fixed: bool = False  # if True, the task must start exactly at earliest_start

    def __post_init__(self) -> None:
        if to_minutes(self.earliest_start) >= to_minutes(self.latest_end):
            raise ValueError("earliest_start must be before latest_end.")

    def fits(self, start: time, duration_minutes: int) -> bool:
        """Return True if a task starting at `start` and lasting `duration_minutes` fits this window."""
        start_min = to_minutes(start)
        if self.is_fixed and start_min != to_minutes(self.earliest_start):
            return False
        return (
            start_min >= to_minutes(self.earliest_start)
            and start_min + duration_minutes <= to_minutes(self.latest_end)
        )


@dataclass
class Task:
    title: str
    duration_minutes: int
    priority: Priority = Priority.MEDIUM
    time_constraint: Optional[TimeConstraint] = None
    category: TaskCategory = TaskCategory.OTHER
    frequency: Frequency = Frequency.DAILY
    weekday: Optional[int] = None  # 0=Monday..6=Sunday; required for WEEKLY tasks
    shareable: bool = False  # can happen at the same time as another pet's shareable task
    completed_dates: set[date] = field(default_factory=set)
    # None means "every matching day". A date pins this instance to one occurrence,
    # which stays due (overdue) until it's completed. Scheduler.complete_task()
    # pins the finished instance and adds the next one.
    due_date: Optional[date] = None

    def __post_init__(self) -> None:
        if self.duration_minutes <= 0:
            raise ValueError("Task duration must be positive.")
        if self.frequency is Frequency.WEEKLY:
            if self.weekday is None and self.due_date is not None:
                self.weekday = self.due_date.weekday()
            if self.weekday not in range(7):
                raise ValueError("Weekly tasks need a weekday from 0 (Monday) to 6 (Sunday).")
            if self.due_date is not None and self.due_date.weekday() != self.weekday:
                raise ValueError("A weekly task's due_date must fall on its weekday.")

    def mark_complete(self, on: Optional[date] = None) -> None:
        """Mark this task as completed for a given day (today by default).

        This only records the completion; use Scheduler.complete_task() to also
        schedule the next occurrence.
        """
        self.completed_dates.add(on or date.today())

    def is_complete_on(self, day: date) -> bool:
        """Return True if this task was completed on the given day."""
        return day in self.completed_dates

    def is_due_on(self, day: date) -> bool:
        """Return True if this task should happen on the given day.

        A dated instance is due from its due date until the day it's completed,
        so a missed occurrence carries forward instead of disappearing.
        """
        if self.due_date is not None:
            return day >= self.due_date and not any(d < day for d in self.completed_dates)
        if self.frequency is Frequency.WEEKLY:
            return day.weekday() == self.weekday
        return True

    def is_overdue_on(self, day: date) -> bool:
        """Return True if this instance was due before `day` and is still not done."""
        return self.due_date is not None and day > self.due_date and self.is_due_on(day)

    def next_due_date(self, after: date) -> date:
        """Return the first day after `after` when this task recurs."""
        if self.frequency is Frequency.WEEKLY:
            return after + timedelta(days=(self.weekday - after.weekday() - 1) % 7 + 1)
        return after + timedelta(days=1)

    def next_occurrence(self, completed_on: date) -> Task:
        """Return a fresh copy of this task due on its next occurrence.

        Counts from the later of the due date and the completion day, so a
        task finished late doesn't produce a next instance that's already past.
        """
        base = max(self.due_date, completed_on) if self.due_date else completed_on
        return replace(self, due_date=self.next_due_date(base), completed_dates=set())

    def has_time_constraint(self) -> bool:
        """Return True if this task has a time constraint."""
        return self.time_constraint is not None

    def is_fixed(self) -> bool:
        """Return True if this task must happen at an exact time."""
        return self.time_constraint is not None and self.time_constraint.is_fixed

    def priority_score(self) -> int:
        """Return a numeric score used for sorting tasks by importance."""
        return self.priority.value


@dataclass
class Pet:
    name: str
    species: str
    age: int
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a care task for this pet.

        Titles must be unique per pet, except for instances of a recurring
        task, which share a title but have different due dates.
        """
        for t in self.tasks:
            if t.title.lower() == task.title.lower() and t.due_date == task.due_date:
                when = f" due {task.due_date.isoformat()}" if task.due_date else ""
                raise ValueError(f"{self.name} already has a task called '{task.title}'{when}.")
        self.tasks.append(task)

    def remove_task(self, task_title: str) -> None:
        """Remove the task with the given title, including all of its recurring instances."""
        remaining = [t for t in self.tasks if t.title.lower() != task_title.lower()]
        if len(remaining) == len(self.tasks):
            raise ValueError(f"{self.name} has no task called '{task_title}'.")
        self.tasks = remaining

    def get_tasks(self) -> list[Task]:
        """Return all tasks for this pet."""
        return list(self.tasks)


@dataclass
class Preference:
    description: str
    preferred_time_of_day: str  # "morning", "afternoon", or "evening"
    weight: int = 1
    categories: list[TaskCategory] = field(default_factory=list)
    pet_name: Optional[str] = None  # None means it applies to every pet

    def __post_init__(self) -> None:
        self.preferred_time_of_day = self.preferred_time_of_day.lower()
        if self.preferred_time_of_day not in TIME_OF_DAY_WINDOWS:
            raise ValueError(
                f"preferred_time_of_day must be one of {', '.join(TIME_OF_DAY_WINDOWS)}."
            )

    def applies_to(self, task: Task, pet: Optional[Pet] = None) -> bool:
        """Return True if this preference is relevant to the given task (and pet)."""
        if self.pet_name is not None and (pet is None or pet.name.lower() != self.pet_name.lower()):
            return False
        return task.category in self.categories

    def window(self) -> tuple[int, int]:
        """Return the preferred (start, end) window in minutes."""
        return TIME_OF_DAY_WINDOWS[self.preferred_time_of_day]


@dataclass
class Owner:
    name: str
    available_minutes: int  # total care time budget for the day
    day_start: time         # tasks are only scheduled between day_start and day_end
    day_end: time
    pets: list[Pet] = field(default_factory=list)
    preferences: list[Preference] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.available_minutes < 0:
            raise ValueError("available_minutes can't be negative.")
        if to_minutes(self.day_start) >= to_minutes(self.day_end):
            raise ValueError("day_start must be before day_end.")

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner. Pet names must be unique."""
        if self.get_pet(pet.name) is not None:
            raise ValueError(f"{self.name} already has a pet named '{pet.name}'.")
        self.pets.append(pet)

    def remove_pet(self, pet_name: str) -> None:
        """Remove the pet with the given name."""
        pet = self.get_pet(pet_name)
        if pet is None:
            raise ValueError(f"{self.name} has no pet named '{pet_name}'.")
        self.pets.remove(pet)

    def get_pet(self, pet_name: str) -> Optional[Pet]:
        """Return the pet with the given name, or None if not found."""
        for pet in self.pets:
            if pet.name.lower() == pet_name.lower():
                return pet
        return None

    def add_preference(self, pref: Preference) -> None:
        """Add a scheduling preference."""
        self.preferences.append(pref)

    def get_all_tasks(self) -> list[tuple[Pet, Task]]:
        """Return every (pet, task) pair across all of this owner's pets."""
        return [(pet, task) for pet in self.pets for task in pet.tasks]


@dataclass
class ScheduledTask:
    task: Task
    pet: Pet
    start_time: time
    end_time: time
    reason: str = ""
    # Minutes since midnight, computed once so scheduling math doesn't keep converting.
    start_min: int = field(init=False, repr=False)
    end_min: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.start_min = to_minutes(self.start_time)
        self.end_min = to_minutes(self.end_time)

    def overlaps(self, other: ScheduledTask) -> bool:
        """Return True if this scheduled task's time range overlaps another's."""
        return self.start_min < other.end_min and other.start_min < self.end_min

    def can_share_time_with(self, task: Task, pet: Pet) -> bool:
        """Return True if `task` for `pet` may happen at the same time as this one."""
        return can_share_time(self.task, self.pet, task, pet)


def can_share_time(task_a: Task, pet_a: Pet, task_b: Task, pet_b: Pet) -> bool:
    """Return True if two tasks may overlap: both shareable and for different pets."""
    return task_a.shareable and task_b.shareable and pet_a.name != pet_b.name


@dataclass
class DailyPlan:
    plan_date: date = field(default_factory=date.today)
    items: list[ScheduledTask] = field(default_factory=list)
    skipped_tasks: list[tuple[Task, Pet, str]] = field(default_factory=list)  # (task, pet, reason)
    warnings: list[str] = field(default_factory=list)  # time conflicts found while planning

    def add_item(self, item: ScheduledTask) -> None:
        """Add a scheduled task to the plan, keeping items ordered by start time."""
        i = len(self.items)
        while i > 0 and self.items[i - 1].start_min > item.start_min:
            i -= 1
        self.items.insert(i, item)

    def total_minutes(self) -> int:
        """Return the owner's busy minutes; tasks done at the same time count once."""
        total, busy_until = 0, -1
        for item in self.items:
            if item.end_min > busy_until:
                total += item.end_min - max(item.start_min, busy_until)
                busy_until = item.end_min
        return total

    def view_tasks(self) -> list[ScheduledTask]:
        """Return the scheduled tasks, ordered by start time (add_item keeps them sorted)."""
        return list(self.items)

    def explain(self) -> str:
        """Return a human-readable explanation of why the plan looks the way it does."""
        lines = [f"Plan for {self.plan_date.isoformat()} ({self.total_minutes()} min scheduled):"]
        if not self.items:
            lines.append("  No tasks scheduled.")
        for item in self.view_tasks():
            lines.append(
                f"  {format_time(item.start_time)}-{format_time(item.end_time)}  "
                f"{item.task.title} for {item.pet.name} "
                f"[{item.task.priority.name.lower()}] - {item.reason}"
            )
        if self.skipped_tasks:
            lines.append("Skipped:")
            for task, pet, reason in self.skipped_tasks:
                lines.append(f"  {task.title} for {pet.name} - {reason}")
        if self.warnings:
            lines.append("Warnings:")
            lines.extend(f"  {w}" for w in self.warnings)
        return "\n".join(lines)


# --- Scheduling -----------------------------------------------------------

class Scheduler:
    """Builds a DailyPlan in three steps:

    1. Choose tasks that fit the time budget, most important first.
    2. Place the chosen tasks, least flexible first (fixed, then narrow windows),
       so flexible tasks can't take a constrained task's only slot.
    3. Use any budget left over (from unplaced or shared-time tasks) for tasks
       that didn't make the cut in step 1.

    Step 1 is greedy by score, shortest first within a score. That already fits
    as many of the most important tasks as possible while leaving the most room
    for less important ones, so the budget is never "wasted" on a lower-priority
    task at the expense of a higher-priority one.
    """

    def __init__(self, owner: Owner, plan_date: Optional[date] = None) -> None:
        self.owner = owner
        self.plan_date = plan_date or date.today()
        self._cache: Optional[dict] = None  # only set while generate_plan() runs

    def generate_plan(self) -> DailyPlan:
        """Build a DailyPlan from the owner's pets, tasks, and preferences."""
        self._cache = {}
        try:
            return self._build_plan()
        finally:
            self._cache = None

    def score_task(self, task: Task, pet: Optional[Pet] = None) -> int:
        """Combine priority with the weights of any preferences that apply to the task."""
        return self._memo(
            ("score", id(task), id(pet)),
            lambda: task.priority_score() * 10
            + sum(p.weight for p in self._matching_prefs(task, pet)),
        )

    def sort_tasks(self, tasks: list[tuple[Pet, Task]]) -> list[tuple[Pet, Task]]:
        """Order tasks by importance: highest score first, then shortest first."""
        return sorted(tasks, key=lambda pt: (-self.score_task(pt[1], pt[0]), pt[1].duration_minutes))

    def sort_by_time(self, items: list[ScheduledTask]) -> list[ScheduledTask]:
        """Return scheduled tasks in chronological order: earliest start first, then earliest end."""
        return sorted(items, key=lambda i: (i.start_min, i.end_min))

    def filter_tasks(self, tasks: list[tuple[Pet, Task]]) -> list[tuple[Pet, Task]]:
        """Return only tasks that are due on the plan date and not already done that day."""
        return [
            (pet, task) for pet, task in tasks
            if task.is_due_on(self.plan_date) and not task.is_complete_on(self.plan_date)
        ]

    def complete_task(self, pet: Pet, task: Task, on: Optional[date] = None) -> Optional[Task]:
        """Mark a task done and add its next occurrence to the pet; return the new instance.

        The finished instance is pinned to the day it was done so it doesn't
        show up again alongside the new one. Completing the same task twice on
        one day does nothing and returns None.
        """
        day = on or self.plan_date
        if task.is_complete_on(day):
            return None
        task.mark_complete(day)
        if task.due_date is None:
            task.due_date = day
        upcoming = task.next_occurrence(day)
        pet.add_task(upcoming)
        return upcoming

    def find_slot(self, task: Task, pet: Pet, plan: DailyPlan) -> Optional[time]:
        """Return the earliest valid start time for a task in the plan, or None if none fits.

        Fixed tasks only ever get their exact time. Other tasks try the pet's
        preferred time-of-day window(s) first, then any allowed time in the day.
        """
        lo, hi = self._window(task)
        windows = []
        if not task.is_fixed():
            for pref in self._matching_prefs(task, pet):
                w_lo, w_hi = pref.window()
                w_lo, w_hi = max(lo, w_lo), min(hi, w_hi)
                # Skip windows the task can't fit in, or that just repeat the full window.
                if w_hi - w_lo >= task.duration_minutes and (w_lo, w_hi) != (lo, hi):
                    windows.append((w_lo, w_hi))
        windows.append((lo, hi))

        for w_lo, w_hi in windows:
            start = self._earliest_gap(task, pet, w_lo, w_hi, plan)
            if start is not None:
                return from_minutes(start)
        return None

    def detect_conflicts(self, plan: DailyPlan) -> list[str]:
        """Return descriptions of tasks in a plan that overlap but aren't allowed to.

        generate_plan() never creates these; this checks plans edited by hand.
        """
        entries = [(i.start_min, i.end_min, i.pet, i.task) for i in plan.items]
        return [self._describe_clash(a, b) for a, b in self._clashes(entries)]

    def detect_time_conflicts(self, tasks: list[tuple[Pet, Task]]) -> list[str]:
        """Return warnings for fixed-time tasks that ask for overlapping times.

        Works for the same pet or different pets (shareable tasks for different
        pets are fine). Only fixed tasks can truly clash, since flexible tasks
        can move. Never raises: the scheduler keeps the more important task and
        these warnings explain what happened to the other one.
        """
        entries = [(*self._window(t), pet, t) for pet, t in tasks if t.is_fixed()]
        return [
            f"Time conflict: {self._describe_clash(a, b)}; only one can be scheduled"
            for a, b in self._clashes(entries)
        ]

    # --- internal helpers ---

    @staticmethod
    def _clashes(entries: list[tuple[int, int, Pet, Task]]) -> list[tuple[tuple, tuple]]:
        """Return pairs of (start, end, pet, task) entries that overlap but can't share time.

        Lightweight sort-and-sweep: after sorting by start, each entry is only
        compared with the entries that start before it ends.
        """
        entries = sorted(entries, key=lambda e: (e[0], e[1]))
        pairs = []
        for i, a in enumerate(entries):
            for b in entries[i + 1:]:
                if b[0] >= a[1]:
                    break  # sorted by start, so nothing later can overlap `a`
                # b starts inside a, so they overlap.
                if not can_share_time(a[3], a[2], b[3], b[2]):
                    pairs.append((a, b))
        return pairs

    def _describe_clash(self, a: tuple, b: tuple) -> str:
        """Describe two overlapping (start, end, pet, task) entries."""
        def label(e: tuple) -> str:
            return f"'{e[3].title}' ({e[2].name}, {self._span(from_minutes(e[0]), from_minutes(e[1]))})"
        return f"{label(a)} overlaps {label(b)}"

    def _build_plan(self) -> DailyPlan:
        """Run the three scheduling steps described in the class docstring and return the plan."""
        plan = DailyPlan(plan_date=self.plan_date)
        budget = self.owner.available_minutes

        # Drop tasks that can never fit today, whatever else is scheduled.
        feasible = []
        for pet, task in self.filter_tasks(self.owner.get_all_tasks()):
            problem = self._infeasible_reason(task)
            if problem:
                plan.skipped_tasks.append((task, pet, problem))
            else:
                feasible.append((pet, task))
        plan.warnings = self.detect_time_conflicts(feasible)

        # 1. Choose by importance within the budget. Shareable fixed tasks for
        #    different pets at the same time happen together, so charge them once.
        ordered = self.sort_tasks(feasible)
        shortest_after = list(accumulate(reversed([t.duration_minutes for _, t in ordered]), min))[::-1]
        chosen, over_budget = [], []
        budget_left = budget
        charged_slots: dict[tuple[int, int], str] = {}  # shared slot -> pet already charged
        for i, (pet, task) in enumerate(ordered):
            if budget_left < shortest_after[i]:
                # Nothing left fits at full cost; step 3 still catches free shared tasks.
                over_budget.extend(ordered[i:])
                break
            slot = self._shared_slot(task)
            shared = slot in charged_slots and charged_slots[slot] != pet.name
            cost = 0 if shared else task.duration_minutes
            if cost <= budget_left:
                chosen.append((pet, task))
                budget_left -= cost
                if slot is not None:
                    charged_slots.setdefault(slot, pet.name)
            else:
                over_budget.append((pet, task))

        # 2. Place least flexible first. 3. Fill in with leftover budget.
        chosen.sort(key=lambda pt: (
            not pt[1].is_fixed(),
            not pt[1].has_time_constraint(),
            self._slack(pt[1]),
            -self.score_task(pt[1], pt[0]),
        ))
        busy = 0  # running total, so we never rescan the plan for it
        for pet, task in chosen + over_budget:
            busy += self._schedule(task, pet, plan, budget - busy)

        return plan

    def _memo(self, key: tuple, compute: Callable[[], Any]) -> Any:
        """Return compute(), reusing the result for the same key while a plan is built."""
        if self._cache is None:
            return compute()
        if key not in self._cache:
            self._cache[key] = compute()
        return self._cache[key]

    def _matching_prefs(self, task: Task, pet: Optional[Pet]) -> list[Preference]:
        """Return the owner's preferences that apply to this task for this pet."""
        return self._memo(
            ("prefs", id(task), id(pet)),
            lambda: [p for p in self.owner.preferences if p.applies_to(task, pet)],
        )

    def _window(self, task: Task) -> tuple[int, int]:
        """Return the (start, end) minutes a task may occupy: the owner's day narrowed by its constraint."""
        lo, hi = to_minutes(self.owner.day_start), to_minutes(self.owner.day_end)
        tc = task.time_constraint
        if tc is None:
            return lo, hi
        if tc.is_fixed:
            start = to_minutes(tc.earliest_start)
            return start, start + task.duration_minutes
        return max(lo, to_minutes(tc.earliest_start)), min(hi, to_minutes(tc.latest_end))

    def _slack(self, task: Task) -> int:
        """Return how many minutes of wiggle room a task has in its window."""
        lo, hi = self._window(task)
        return hi - lo - task.duration_minutes

    def _shared_slot(self, task: Task) -> Optional[tuple[int, int]]:
        """Return the exact (start, end) minutes of a shareable fixed task, else None."""
        return self._window(task) if task.shareable and task.is_fixed() else None

    @staticmethod
    def _span(start: time, end: time) -> str:
        """Format a time range as HH:MM-HH:MM."""
        return f"{format_time(start)}-{format_time(end)}"

    def _infeasible_reason(self, task: Task) -> Optional[str]:
        """Return why a task can never be scheduled today, or None if it could be."""
        day_lo, day_hi = to_minutes(self.owner.day_start), to_minutes(self.owner.day_end)
        tc = task.time_constraint
        # Messages are only built on the branch that returns them.
        if tc is not None:
            if not tc.fits(tc.earliest_start, task.duration_minutes):
                return f"its time window ({self._span(tc.earliest_start, tc.latest_end)}) is shorter than the task"
            lo, hi = self._window(task)
            if tc.is_fixed and (lo < day_lo or hi > day_hi):
                return (
                    f"its fixed time ({format_time(tc.earliest_start)}) is outside your day "
                    f"({self._span(self.owner.day_start, self.owner.day_end)})"
                )
            if hi - lo < task.duration_minutes:
                return (
                    f"its time window ({self._span(tc.earliest_start, tc.latest_end)}) doesn't fit "
                    f"inside your day ({self._span(self.owner.day_start, self.owner.day_end)})"
                )
        elif self._slack(task) < 0:
            return f"it's longer than your whole day ({self._span(self.owner.day_start, self.owner.day_end)})"
        if task.duration_minutes > self.owner.available_minutes:
            return f"it's longer than your {self.owner.available_minutes}-min budget"
        return None

    def _no_slot_reason(self, task: Task) -> str:
        """Explain why a feasible task couldn't be placed in this plan."""
        if task.is_fixed():
            return f"its fixed time ({format_time(task.time_constraint.earliest_start)}) is already taken"
        return "no open time slot fits it"

    def _earliest_gap(
        self, task: Task, pet: Pet, lo: int, hi: int, plan: DailyPlan
    ) -> Optional[int]:
        """Return the earliest start in [lo, hi] where the task fits without a disallowed overlap.

        [lo, hi] is always inside the task's own window, so its time constraint
        holds for any start found here and doesn't need re-checking.
        """
        duration = task.duration_minutes
        if hi - lo < duration:
            return None
        busy = [(i.start_min, i.end_min) for i in plan.items if not i.can_share_time_with(task, pet)]
        # A task can only start at the window start or right after a blocking item.
        candidates = sorted({lo} | {end for _, end in busy})
        for start in candidates:
            end = start + duration
            if start < lo or end > hi:
                continue
            if all(end <= b_start or start >= b_end for b_start, b_end in busy):
                return start
        return None

    def _schedule(self, task: Task, pet: Pet, plan: DailyPlan, minutes_left: int) -> int:
        """Add a task to the plan if it has a slot and fits the budget; return the busy minutes it added.

        Time shared with tasks already in the plan doesn't count against the budget.
        """
        budget_reason = f"not enough time left in the {self.owner.available_minutes}-min budget"
        # Only shareable tasks can cost less than their duration, so skip the slot search for the rest.
        if not task.shareable and task.duration_minutes > minutes_left:
            plan.skipped_tasks.append((task, pet, budget_reason))
            return 0
        start = self.find_slot(task, pet, plan)
        if start is None:
            plan.skipped_tasks.append((task, pet, self._no_slot_reason(task)))
            return 0
        item = ScheduledTask(task, pet, start, from_minutes(to_minutes(start) + task.duration_minutes))
        shared_with = [i for i in plan.items if i.overlaps(item)]
        added = task.duration_minutes - self._covered(item, shared_with)
        if added > minutes_left:
            plan.skipped_tasks.append((task, pet, budget_reason))
            return 0
        item.reason = self._reason(task, pet, item.start_min, shared_with)
        plan.add_item(item)
        return added

    @staticmethod
    def _covered(item: ScheduledTask, others: list[ScheduledTask]) -> int:
        """Return how many of item's minutes `others` (sorted by start) already cover, counted once."""
        covered, covered_until = 0, item.start_min
        for other in others:
            start, end = max(other.start_min, covered_until), min(other.end_min, item.end_min)
            if end > start:
                covered += end - start
                covered_until = end
        return covered

    def _reason(
        self, task: Task, pet: Pet, start_min: int, shared_with: list[ScheduledTask]
    ) -> str:
        """Explain why a task landed where it did."""
        parts = [f"{task.priority.name.lower()} priority"]
        tc = task.time_constraint
        if task.is_fixed():
            parts.append(f"fixed at {format_time(tc.earliest_start)}")
        elif tc is not None:
            parts.append(
                f"must happen between {format_time(tc.earliest_start)} and {format_time(tc.latest_end)}"
            )
        if task.frequency is Frequency.WEEKLY:
            parts.append("weekly task")
        if task.is_overdue_on(self.plan_date):
            parts.append(f"overdue since {task.due_date.strftime('%a %b %d')}")
        if not task.is_fixed():
            for pref in self._matching_prefs(task, pet):
                w_lo, w_hi = pref.window()
                if w_lo <= start_min < w_hi:
                    parts.append(f"matches preference: {pref.description}")
                else:
                    parts.append(f"couldn't fit preferred {pref.preferred_time_of_day}")
        for other in shared_with:
            parts.append(f"done alongside {other.pet.name}'s {other.task.title.lower()}")
        return "; ".join(parts)
