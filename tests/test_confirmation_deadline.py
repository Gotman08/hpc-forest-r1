import time

from hpc_forest.codex_mailbox import (
    EFFORT,
    MODEL,
    TOKEN_CEILING,
    CodexMailboxBackend,
    initialize_channel,
    make_request,
)
from hpc_forest.controller import Controller, create_workspace
from hpc_forest.core import Mission


def test_queued_native_generation_cannot_use_confirmation_time(tmp_path, config):
    source = tmp_path / "tree"
    (source / "src").mkdir(parents=True)
    (source / "src/main.c").write_text("int unchanged;\n")
    mission = Mission("trial", "e1:A", "local-1", 1, "A", "base", None, "R/A", 1, 1, str(source))
    channel = tmp_path / "mailbox"
    initialize_channel(channel, "a" * 32, "test")
    config["codex"] = {"model": MODEL, "reasoning_effort": EFFORT,
                       "mailbox_dir": str(channel), "session_id": "a" * 32}
    config["budget"].update(mission_tokens=TOKEN_CEILING, generation_seconds=600)
    context = {"deadline": time.time() + 120, "generation_deadline": time.time() + 5}
    request = make_request(mission, context, config)
    assert request["expires_at"] == context["generation_deadline"]
    context["generation_deadline"] = time.time() - 1
    generated = CodexMailboxBackend().generate(mission, context, config, tmp_path)
    assert generated.tokens == 0 and generated.usage["llm_calls"] == 0
    assert not list((channel / "requests").iterdir())
    assert (source / "src/main.c").read_text() == "int unchanged;\n"


def test_search_stops_in_reserved_window_and_confirmation_still_runs(tmp_path, config, need_compiler):
    config["budget"]["confirmation_seconds"] = 60
    root = create_workspace(tmp_path / "campaign", config)
    with Controller(root) as controller:
        controller.run(max_batches=0)
        assert controller.evaluator.deadline == controller.db.get("deadline") - 60
        controller.db.set("deadline", time.time() + 55)
        result = controller.run()
        assert result["status"] == "budget_exhausted"
        assert not controller.db.rows("SELECT id FROM trials")
        best = controller.confirm()
        assert best["is_baseline"]
        assert controller.db.evaluations("confirmation", 1)[0]["outcome"]["correct"]
        assert controller.evaluator.deadline == controller.db.get("deadline")
