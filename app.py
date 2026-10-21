from datetime import time

import streamlit as st

from pawpal_system import Owner, Pet, Priority, Scheduler, Task

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

# Streamlit reruns this whole script on every click, so keep the Owner in
# st.session_state. Only create it the first time; later runs reuse it.
if "owner" not in st.session_state:
    st.session_state.owner = Owner(
        name="Jordan",
        available_minutes=120,
        day_start=time(7, 0),
        day_end=time(21, 0),
    )
owner = st.session_state.owner

st.title("🐾 PawPal+")

st.markdown(
    """
Welcome to the PawPal+ starter app.

This file is intentionally thin. It gives you a working Streamlit app so you can start quickly,
but **it does not implement the project logic**. Your job is to design the system and build it.

Use this app as your interactive demo once your backend classes/functions exist.
"""
)

with st.expander("Scenario", expanded=True):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
for their pet(s) based on constraints like time, priority, and preferences.

You will design and implement the scheduling logic and connect it to this Streamlit UI.
"""
    )

with st.expander("What you need to build", expanded=True):
    st.markdown(
        """
At minimum, your system should:
- Represent pet care tasks (what needs to happen, how long it takes, priority)
- Represent the pet and the owner (basic info and preferences)
- Build a plan/schedule for a day that chooses and orders tasks based on constraints
- Explain the plan (why each task was chosen and when it happens)
"""
    )

st.divider()

st.subheader("Owner")
owner.name = st.text_input("Owner name", value=owner.name)

st.markdown("### Pets")
col1, col2, col3 = st.columns(3)
with col1:
    pet_name = st.text_input("Pet name", value="Mochi")
with col2:
    species = st.selectbox("Species", ["dog", "cat", "other"])
with col3:
    age = st.number_input("Age (years)", min_value=0, max_value=40, value=2)

if st.button("Add pet"):
    if not pet_name.strip():
        st.error("Please enter a pet name.")
    else:
        try:
            owner.add_pet(Pet(name=pet_name.strip(), species=species, age=int(age)))
            st.success(f"Added {pet_name.strip()}.")
        except ValueError as e:
            st.error(str(e))

if owner.pets:
    st.table([{"name": p.name, "species": p.species, "age": p.age} for p in owner.pets])
else:
    st.info("No pets yet. Add one above.")

st.markdown("### Tasks")

if not owner.pets:
    st.caption("Add a pet first, then you can give it tasks.")
else:
    task_pet = st.selectbox("For pet", [p.name for p in owner.pets])
    col1, col2, col3 = st.columns(3)
    with col1:
        task_title = st.text_input("Task title", value="Morning walk")
    with col2:
        duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
    with col3:
        priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)

    if st.button("Add task"):
        if not task_title.strip():
            st.error("Please enter a task title.")
        else:
            try:
                owner.get_pet(task_pet).add_task(Task(
                    title=task_title.strip(),
                    duration_minutes=int(duration),
                    priority=Priority[priority.upper()],
                ))
                st.success(f"Added '{task_title.strip()}' for {task_pet}.")
            except ValueError as e:
                st.error(str(e))

all_tasks = owner.get_all_tasks()
if all_tasks:
    st.write("Current tasks:")
    st.table([
        {
            "pet": pet.name,
            "title": task.title,
            "duration_minutes": task.duration_minutes,
            "priority": task.priority.name.lower(),
        }
        for pet, task in all_tasks
    ])
elif owner.pets:
    st.info("No tasks yet. Add one above.")

st.divider()

st.subheader("Build Schedule")

if st.button("Generate schedule"):
    if not all_tasks:
        st.warning("Add at least one task before generating a schedule.")
    else:
        plan = Scheduler(owner).generate_plan()
        st.markdown(f"**Today's schedule for {owner.name}** ({plan.plan_date.strftime('%A, %B %d')})")

        for warning in plan.warnings:
            st.warning(warning)

        if plan.items:
            st.table([
                {
                    "time": f"{item.start_time.strftime('%H:%M')}-{item.end_time.strftime('%H:%M')}",
                    "task": item.task.title,
                    "pet": item.pet.name,
                    "why": item.reason,
                }
                for item in plan.view_tasks()
            ])
        else:
            st.info("Nothing could be scheduled today.")

        if plan.skipped_tasks:
            st.markdown("**Skipped**")
            for task, pet, reason in plan.skipped_tasks:
                st.write(f"- {task.title} ({pet.name}): {reason}")

        st.caption(f"{plan.total_minutes()} of {owner.available_minutes} available minutes used.")
