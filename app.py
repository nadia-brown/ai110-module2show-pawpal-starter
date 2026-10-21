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

PRIORITY_LABELS = {
    Priority.HIGH: "🔴 High",
    Priority.MEDIUM: "🟡 Medium",
    Priority.LOW: "🟢 Low",
}

all_tasks = owner.get_all_tasks()
scheduler = Scheduler(owner)

if all_tasks:
    st.markdown("#### Current tasks")
    col1, col2, col3 = st.columns(3)
    with col1:
        pet_filter = st.selectbox("Show pet", ["All pets"] + [p.name for p in owner.pets])
    with col2:
        sort_by = st.selectbox("Sort by", ["Priority", "Duration", "Pet"])
    with col3:
        st.write("")  # nudge the checkbox down to line up with the selectboxes
        due_only = st.checkbox("Due today only", value=False)

    # Filter first, then sort, using the same logic the scheduler uses.
    shown = all_tasks
    if pet_filter != "All pets":
        shown = [(pet, task) for pet, task in shown if pet.name == pet_filter]
    if due_only:
        shown = scheduler.filter_tasks(shown)

    if sort_by == "Priority":
        shown = scheduler.sort_tasks(shown)
    elif sort_by == "Duration":
        shown = sorted(shown, key=lambda pt: pt[1].duration_minutes)
    else:
        shown = sorted(shown, key=lambda pt: (pt[0].name.lower(), -pt[1].priority_score()))

    if shown:
        due_today = {id(task) for _, task in scheduler.filter_tasks(shown)}
        st.table([
            {
                "Pet": pet.name,
                "Task": task.title,
                "Duration": f"{task.duration_minutes} min",
                "Priority": PRIORITY_LABELS[task.priority],
                "Due today": "✅" if id(task) in due_today else "—",
            }
            for pet, task in shown
        ])
        total = sum(task.duration_minutes for _, task in shown)
        st.caption(f"Showing {len(shown)} of {len(all_tasks)} tasks · {total} min total")
    else:
        st.info("No tasks match these filters.")
elif owner.pets:
    st.info("No tasks yet. Add one above.")

st.divider()

st.subheader("Build Schedule")

if st.button("Generate schedule", type="primary"):
    if not all_tasks:
        st.warning("Add at least one task before generating a schedule.")
    else:
        plan = scheduler.generate_plan()
        used = plan.total_minutes()
        st.markdown(f"**Today's schedule for {owner.name}** ({plan.plan_date.strftime('%A, %B %d')})")

        col1, col2, col3 = st.columns(3)
        col1.metric("Scheduled", len(plan.items))
        col2.metric("Skipped", len(plan.skipped_tasks))
        col3.metric("Time used", f"{used} / {owner.available_minutes} min")
        st.progress(min(used / owner.available_minutes, 1.0) if owner.available_minutes else 0.0)

        for warning in plan.warnings:
            st.warning(f"⚠️ {warning}")

        if plan.items:
            if plan.skipped_tasks:
                st.info(f"Scheduled {len(plan.items)} task(s); {len(plan.skipped_tasks)} didn't fit.")
            else:
                st.success(f"All {len(plan.items)} task(s) fit into today's schedule! 🎉")
            st.table([
                {
                    "Time": f"{item.start_time.strftime('%H:%M')} – {item.end_time.strftime('%H:%M')}",
                    "Task": item.task.title,
                    "Pet": item.pet.name,
                    "Priority": PRIORITY_LABELS[item.task.priority],
                    "Why": item.reason,
                }
                for item in scheduler.sort_by_time(plan.view_tasks())
            ])
        else:
            st.error("Nothing could be scheduled today.")

        if plan.skipped_tasks:
            st.markdown("#### Skipped tasks")
            st.table([
                {
                    "Task": task.title,
                    "Pet": pet.name,
                    "Priority": PRIORITY_LABELS[task.priority],
                    "Reason": reason,
                }
                for task, pet, reason in plan.skipped_tasks
            ])
