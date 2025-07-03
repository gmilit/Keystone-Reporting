#!/usr/bin/env -S uv run --script
"""
Generate three JPEG graphs from Jira issues in project FS and upload to Slack.

Graphs (all use Monday–Sunday weeks, last 9 weeks):
1. Weekly Support Tickets – stacked Resolved (green) / Unresolved (red)
2. Weekly P1/P2 Incidents
3. Stacked Weekly mix of “Type of Work”

Run head-less in GitHub Actions or interactively on your laptop.
"""

from __future__ import annotations
import os, datetime, argparse
import pandas as pd
import matplotlib.pyplot as plt
from jira import JIRA
from slack_sdk import WebClient
from dotenv import load_dotenv
import matplotlib.dates as mdates

load_dotenv()
plt.switch_backend("Agg")  # safe for CI

# ────────────────────────────── helpers

JIRA_GREEN = "#8cc14c"  # Jira “success” green
JIRA_RED = "#d04437"  # Jira “danger” red
jira = JIRA(
    os.getenv("JIRA_URL"),
    basic_auth=(os.getenv("JIRA_EMAIL"), os.getenv("JIRA_API_TOKEN")),
)


def monday_weeks_ago(n: int) -> datetime.date:
    """Return the Monday of the week that is *n* weeks ago (0 = this week)."""
    today = datetime.date.today()
    this_monday = today - datetime.timedelta(days=today.weekday())
    return this_monday - datetime.timedelta(weeks=n)


def sunday_weeks_ago(n: int) -> datetime.date:
    """Return the **Sunday** of the week that is *n* weeks ago (0 = this week)."""
    today = datetime.date.today()
    # Monday=0 … Sunday=6  →  days since **last Sunday**
    days_since_sunday = (today.weekday() + 1) % 7
    this_sunday = today - datetime.timedelta(days=days_since_sunday)
    return this_sunday - datetime.timedelta(weeks=n)


def weekly_support_table(issues: list) -> pd.DataFrame:
    rows = [{"created": i.fields.created,
             "resolved": i.fields.status.name.lower() == "done"}
            for i in issues]

    df = pd.DataFrame(rows)

    dt = pd.to_datetime(df["created"], utc=True).dt.tz_convert(None)
    df["week"] = dt.dt.to_period("W-SAT").dt.start_time

    weekly = (
        df.groupby(["week", "resolved"])
        .size()
        .unstack(fill_value=0)
        .rename(columns={False: "Unresolved", True: "Resolved"})
        .sort_index()
    )

    weekly.columns.name = None  # ← drop the index name, kill extra legend label
    return weekly


def weekly_series(issues: list) -> pd.Series:
    dates = pd.to_datetime([i.fields.created for i in issues], utc=True).tz_convert(None)
    weeks = dates.to_period("W-SAT").start_time
    return weeks.value_counts().sort_index()


def save_fig(data, title: str, filename: str,
             *, stacked=False, colors=None):
    # ------------------------------------------------- plot
    if isinstance(data, pd.DataFrame):
        ax = data.plot(kind="bar", stacked=stacked,
                       figsize=(9, 4), color=colors)
    else:
        ax = data.plot(kind="bar", figsize=(9, 4), color=colors)

    ax.set_title(title)
    ax.set_xlabel("")
    ax.set_ylabel("Tickets")

    # ------------------------------------------------- pretty X labels
    if isinstance(data.index, (pd.DatetimeIndex, pd.PeriodIndex)):
        # convert PeriodIndex to Timestamp first
        idx = (data.index.to_timestamp() if isinstance(data.index, pd.PeriodIndex)
               else data.index)
        labels = [d.strftime("%Y-%m-%d") for d in idx]

        ax.set_xticks(range(len(labels)))  # integer positions
        ax.set_xticklabels(labels, rotation=45,
                           horizontalalignment="right")

    plt.tight_layout()
    plt.savefig(filename, dpi=200, format="jpg")
    plt.close()


def weekly_support_graph(start: datetime.date):
    jql_window = f'project = FS AND created >= "{start.isoformat()}"'
    support_issues = jira.search_issues(
        f"{jql_window}",
        maxResults=False,
        fields="created,status",
    )
    support_df = weekly_support_table(support_issues)
    save_fig(support_df,
             "Weekly Support Tickets (Resolved vs Unresolved)",
             "support.jpg",
             stacked=True,
             colors=[JIRA_RED, JIRA_GREEN],
             )



def weekly_rec_incidents_graph(start: datetime.date):
    # 2️⃣ Rec incidents
    jql_window = f'project = FS AND created >= "{start.isoformat()}"'
    rec_issues = jira.search_issues(
        f'{jql_window} AND summary ~ "REC ISSUE"',
        maxResults=False,
        fields="created",
    )
    rec_series = weekly_series(rec_issues)
    save_fig(rec_series, "Weekly Rec Incidents", "p1p2.jpg", colors=JIRA_GREEN)
# ────────────────────────────── main

def main(show: bool = False):
    start = sunday_weeks_ago(8)  # 0..8 → 9 weeks inclusive
    jql_window = f'project = FS AND created >= "{start.isoformat()}"'

    weekly_support_graph(start)
    weekly_rec_incidents_graph(start)

    # # 3️⃣ Stacked work-type mix
    # wtf = os.getenv("WORK_TYPE_FIELD_ID")  # custom field key
    # work_issues = jira.search_issues(
    #     f"{jql_window}",
    #     maxResults=False,
    #     fields=f"created,{wtf}",
    # )
    # rows = [
    #     {
    #         "created": i.fields.created,
    #         "work_type": getattr(i.fields, wtf) or "Unspecified",
    #     }
    #     for i in work_issues
    # ]
    # wdf = pd.DataFrame(rows)
    # wdf["created"] = pd.to_datetime(wdf["created"])
    # wdf["week"] = wdf["created"].dt.to_period("W-SAT").dt.start_time
    # stacked = (
    #     wdf.pivot_table(
    #         index="week", columns="work_type", values="created", aggfunc="count"
    #     )
    #     .fillna(0)
    #     .sort_index()
    # )
    # save_fig(stacked, "Weekly Work-Type Mix", "mix.jpg", stacked=True)

    # # ── preview locally with --show
    # if show:
    #     plt.switch_backend("MacOSX" if os.uname().sysname == "Darwin" else "TkAgg")
    #     for f in ("support.jpg", "p1p2.jpg", "mix.jpg"):
    #         img = plt.imread(f)
    #         plt.figure(); plt.imshow(img); plt.axis("off")
    #     plt.show()
    #
    # # ── upload when SLACK_BOT_TOKEN is present (CI & local)
    # token = os.getenv("SLACK_BOT_TOKEN")
    # if token:
    #     slack = WebClient(token=token)
    #     channel = os.getenv("SLACK_CHANNEL")
    #     for f in ("support.jpg", "p1p2.jpg", "mix.jpg"):
    #         slack.files_upload(
    #             channels=channel,
    #             file=f,
    #             title=f.replace(".jpg", ""),
    #             initial_comment=f"*{f.replace('.jpg', '').title()}*",
    #         )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--show", action="store_true", help="Open graphs interactively for tweaking."
    )
    main(**vars(ap.parse_args()))
