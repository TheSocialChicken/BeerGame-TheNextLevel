"""Generate post-game Quarto reports from GameState."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

from core.models import GameState, PlayerRole

TEMPLATE = Path(__file__).parent / "classic_report.qmd"


def build_report_data(state: GameState) -> dict:
    """Flatten GameState into the JSON schema expected by classic_report.qmd."""
    roles = [r.value for r in PlayerRole]

    # Build per-round history from demand_history + player cost snapshots.
    # NOTE: cumulative_cost is the final value; full history requires the engine
    # to have emitted round snapshots. We emit what we have.
    round_history = []
    for i, demand in enumerate(state.customer_demand_history):
        round_history.append(
            {
                "round": i + 1,
                "customer_demand": demand,
                "cumulative_cost": {
                    r.value: state.players[r].cumulative_cost
                    for r in PlayerRole
                    if r in state.players
                },
                "inventory": {
                    r.value: state.players[r].inventory
                    for r in PlayerRole
                    if r in state.players
                },
                "orders": {
                    r.value: state.players[r].last_order
                    for r in PlayerRole
                    if r in state.players
                },
            }
        )

    return {
        "game_id": state.game_id,
        "variant": state.variant,
        "rounds_played": state.current_round,
        "roles": roles,
        "round_history": round_history,
        "final_costs": {
            r.value: state.players[r].cumulative_cost
            for r in PlayerRole
            if r in state.players
        },
    }


def render_report(
    state: GameState,
    output_dir: Path | str,
    formats: list[Literal["html", "pdf"]] | None = None,
) -> list[Path]:
    """
    Render the Quarto report for *state* into *output_dir*.
    Returns paths to the generated files.
    Requires Quarto + Python deps (pandas, matplotlib) in the environment.
    """
    formats = formats or ["html"]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report_data = build_report_data(state)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, dir=output_dir
    ) as fh:
        json.dump(report_data, fh)
        data_file = Path(fh.name)

    outputs: list[Path] = []
    for fmt in formats:
        out_path = output_dir / f"game_{state.game_id[:8]}_{fmt}.{fmt}"
        cmd = [
            "quarto",
            "render",
            str(TEMPLATE),
            "--to",
            fmt,
            "--output",
            str(out_path),
            "-P",
            f"game_id:{state.game_id}",
            "-P",
            f"data_file:{data_file}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"Quarto render failed for {fmt}:\n{result.stderr}"
            )
        outputs.append(out_path)

    data_file.unlink(missing_ok=True)
    return outputs
