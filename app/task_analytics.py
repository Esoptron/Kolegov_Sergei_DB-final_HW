from collections import Counter
from io import BytesIO
from threading import Lock
from uuid import UUID

import pandas as pd
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Task, TaskStatus, Topic, User
from app.schemas import AssigneeCount, ChartGroup, StatusCount, TaskFilters, TaskSummary, TopicCount
from app.task_queries import task_conditions


STATUS_LABELS = {
    TaskStatus.NEW: "Новые",
    TaskStatus.IN_PROGRESS: "В работе",
    TaskStatus.BLOCKED: "Заблокированы",
    TaskStatus.DONE: "Сделаны",
}
CHART_TITLES = {
    ChartGroup.STATUS: "Задачи по статусам",
    ChartGroup.TOPIC: "Задачи по темам",
    ChartGroup.ASSIGNEE: "Задачи по исполнителям",
}
CHART_LIMIT = 12
chart_lock = Lock()


def summarize_tasks(db: Session, user_id: UUID, filters: TaskFilters) -> TaskSummary:
    statement = (
        select(
            Task.status, Topic.id.label("topic_id"), Topic.name.label("topic"),
            User.id.label("assignee_id"), User.username.label("assignee"),
            func.count(Task.id).label("count"),
        )
        .select_from(Task)
        .join(Topic, Task.topic_id == Topic.id)
        .outerjoin(User, Task.assignee_id == User.id)
        .where(*task_conditions(user_id, filters))
        .group_by(Task.status, Topic.id, Topic.name, User.id, User.username)
    )
    rows = db.execute(statement).mappings()
    frame = pd.DataFrame.from_records(
        rows, columns=["status", "topic_id", "topic", "assignee_id", "assignee", "count"],
    )

    total = int(frame["count"].sum())
    status_counts = frame.groupby("status")["count"].sum()
    completed = int(status_counts.get(TaskStatus.DONE.value, 0))
    topics = (
        frame.groupby(["topic_id", "topic"], as_index=False)["count"].sum()
        .sort_values(["count", "topic", "topic_id"], ascending=[False, True, True])
    )
    assignees = (
        frame.groupby(["assignee_id", "assignee"], as_index=False, dropna=False)["count"].sum()
        .sort_values(["count", "assignee"], ascending=[False, True])
    )
    return TaskSummary(
        total=total,
        completed=completed,
        completion_percent=round(100 * completed / total, 2) if total else 0.0,
        by_status=[
            StatusCount(status=status, count=int(status_counts.get(status.value, 0)))
            for status in TaskStatus
        ],
        by_topic=[
            TopicCount(topic_id=row.topic_id, topic=row.topic, count=row.count)
            for row in topics.itertuples(index=False)
        ],
        by_assignee=[
            AssigneeCount(
                assignee_id=None if pd.isna(row.assignee_id) else row.assignee_id,
                assignee=None if pd.isna(row.assignee) else row.assignee,
                count=row.count,
            )
            for row in assignees.itertuples(index=False)
        ],
    )


def chart_rows(summary: TaskSummary, group: ChartGroup) -> list[tuple[str, int]]:
    if group == ChartGroup.STATUS:
        return [(STATUS_LABELS[item.status], item.count) for item in summary.by_status]
    if group == ChartGroup.TOPIC:
        labels = [item.topic[:32] + "…" if len(item.topic) > 32 else item.topic for item in summary.by_topic]
        duplicates = Counter(labels)
        return [
            (f"{label} · {str(item.topic_id)[:8]}" if duplicates[label] > 1 else label, item.count)
            for label, item in zip(labels, summary.by_topic, strict=True)
        ]
    return [(item.assignee or "Без исполнителя", item.count) for item in summary.by_assignee]


def render_chart(summary: TaskSummary, group: ChartGroup) -> bytes:
    rows = chart_rows(summary, group)
    with chart_lock, BytesIO() as buffer:
        height = max(2.5, 1.5 + 0.38 * min(len(rows), CHART_LIMIT))
        figure = Figure(figsize=(8, height), layout="constrained")
        axes = figure.subplots()
        axes.set_title(CHART_TITLES[group], loc="left", pad=16, fontweight="bold")
        if summary.total:
            labels, counts = zip(*rows[:CHART_LIMIT], strict=True)
            positions = range(len(labels))
            bars = axes.barh(positions, counts, color="#326e89")
            axes.set_yticks(positions, labels, parse_math=False)
            axes.bar_label(bars, padding=5)
            axes.invert_yaxis()
            axes.spines[["top", "right", "left"]].set_visible(False)
            axes.set_xlim(0, max(counts) * 1.2 + 0.5)
            axes.xaxis.set_major_locator(MaxNLocator(integer=True))
            caption = (
                f"Количество задач · первые {CHART_LIMIT} из {len(rows)} групп"
                if len(rows) > CHART_LIMIT else "Количество задач"
            )
            axes.set_xlabel(caption)
        else:
            axes.set_axis_off()
            axes.text(0.5, 0.5, "Задач по выбранным фильтрам пока нет", ha="center", va="center")
        figure.savefig(buffer, format="png", dpi=135)
        return buffer.getvalue()
