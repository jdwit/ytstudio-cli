"""Interactive comment moderation TUI using Textual."""

from __future__ import annotations

from typing import ClassVar

import typer
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Footer, Header, Label

from ytstudio.commands.comments import (
    Comment,
    ModerationStatus,
    SortOrder,
    _set_moderation_status,
    fetch_comments,
)
from ytstudio.services import get_data_service
from ytstudio.ui import console, truncate


class ModerationAction:
    PUBLISH = "publish"
    REJECT = "reject"
    NONE = ""


class ModerateTUI(App):
    CSS = """
    #status { dock: bottom; height: 1; background: $surface; padding: 0 1; }
    #status.has-actions { background: $warning; color: $text; }
    DataTable { height: 1fr; }
    DataTable > .datatable--cursor { background: $accent; }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("enter", "publish", "Publish", show=True),
        Binding("h", "hide", "Reject", show=True),
        Binding("space", "toggle", "Toggle", show=True),
        Binding("a", "publish_all", "Publish All", show=True),
        Binding("q", "quit_app", "Quit & Apply", show=True),
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, comments: list[Comment]):
        super().__init__()
        self.comments = {c.id: c for c in comments}
        self.actions: dict[str, str] = {}
        self.applied_publish = 0
        self.applied_reject = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield DataTable(cursor_type="row")
            yield Label("No pending actions", id="status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Action", "Author", "Comment", "Likes", "Age")
        for comment in self.comments.values():
            table.add_row(
                "",
                comment.author,
                truncate(comment.text, 80),
                str(comment.likes),
                comment.published_at[:10],
                key=comment.id,
            )
        self.title = f"Comment Moderation ({len(self.comments)} held)"

    def _update_row_action(self, comment_id: str) -> None:
        table = self.query_one(DataTable)
        action = self.actions.get(comment_id, "")
        label = {"publish": "✅ publish", "reject": "❌ reject"}.get(action, "")
        row_idx = table.get_row_index(comment_id)
        table.update_cell_at((row_idx, 0), label)
        self._update_status()

    def _update_status(self) -> None:
        status = self.query_one("#status", Label)
        publish_count = sum(1 for a in self.actions.values() if a == ModerationAction.PUBLISH)
        reject_count = sum(1 for a in self.actions.values() if a == ModerationAction.REJECT)
        parts = []
        if publish_count:
            parts.append(f"{publish_count} to publish")
        if reject_count:
            parts.append(f"{reject_count} to reject")
        if parts:
            status.update(", ".join(parts) + " — q to apply")
            status.add_class("has-actions")
        else:
            status.update("No pending actions")
            status.remove_class("has-actions")

    def _get_cursor_id(self) -> str | None:
        table = self.query_one(DataTable)
        if table.row_count == 0:
            return None
        return str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)

    def action_publish(self) -> None:
        cid = self._get_cursor_id()
        if cid:
            self.actions[cid] = ModerationAction.PUBLISH
            self._update_row_action(cid)
            table = self.query_one(DataTable)
            table.action_cursor_down()

    def action_hide(self) -> None:
        cid = self._get_cursor_id()
        if cid:
            self.actions[cid] = ModerationAction.REJECT
            self._update_row_action(cid)
            table = self.query_one(DataTable)
            table.action_cursor_down()

    def action_toggle(self) -> None:
        cid = self._get_cursor_id()
        if cid:
            current = self.actions.get(cid, "")
            if current:
                del self.actions[cid]
            else:
                self.actions[cid] = ModerationAction.PUBLISH
            self._update_row_action(cid)

    def action_publish_all(self) -> None:
        for cid in self.comments:
            self.actions[cid] = ModerationAction.PUBLISH
            self._update_row_action(cid)

    def action_quit_app(self) -> None:
        self._apply_actions()

    def action_cancel(self) -> None:
        self.exit()

    @work(thread=True)
    def _apply_actions(self) -> None:
        publish_ids = [cid for cid, a in self.actions.items() if a == ModerationAction.PUBLISH]
        reject_ids = [cid for cid, a in self.actions.items() if a == ModerationAction.REJECT]

        if publish_ids:
            self.applied_publish = _set_moderation_status(publish_ids, "published")
        if reject_ids:
            self.applied_reject = _set_moderation_status(reject_ids, "rejected")

        self.call_from_thread(self.exit)


def moderate(
    video_id: str = typer.Option(None, "--video", "-v", help="Filter by video ID"),
    limit: int = typer.Option(100, "--limit", "-n", help="Max comments to load"),
):
    """Interactive TUI for batch comment moderation"""
    service = get_data_service()
    comments = fetch_comments(service, video_id, limit, SortOrder.time, ModerationStatus.held)

    if not comments:
        console.print("[green]No held comments to review[/green]")
        raise typer.Exit()

    tui = ModerateTUI(comments)
    tui.run()

    # Print summary after exit
    total = tui.applied_publish + tui.applied_reject
    if total:
        console.print(
            f"[green]{tui.applied_publish} published, {tui.applied_reject} rejected[/green]"
        )
    else:
        console.print("[dim]No changes applied[/dim]")
