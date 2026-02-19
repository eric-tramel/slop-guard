"""Tests for slop-guard analysis engine and CLI."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

from slop_guard import HYPERPARAMETERS, _analyze

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CLEAN_PROSE = textwrap.dedent("""\
    The compiler translates source code into machine instructions. It
    starts by tokenizing the input stream, breaking raw characters into
    meaningful symbols that a parser then assembles into an abstract
    syntax tree.

    Why bother with so many stages? Each one narrows the problem. The
    tree mirrors grammatical structure but says nothing about registers
    or calling conventions. Later passes lower it into a flat
    intermediate form where constant folding and dead-code elimination
    can operate without worrying about syntax.

    Register allocation is the hard part. The allocator must map an
    unbounded set of virtual names onto a handful of physical registers,
    spilling to the stack when it runs out. Graph coloring works, but
    linear scan is faster for JIT compilers that need answers quickly.

    After allocation the backend emits relocatable object code. A linker
    glues the pieces together, resolves symbols, and writes the final
    executable. Done.
""")

SLOPPY_PROSE = textwrap.dedent("""\
    It's worth noting that this groundbreaking, revolutionary journey
    delves into the comprehensive landscape of innovation. Furthermore,
    this seamless, holistic approach leverages cutting-edge technology to
    unlock unprecedented potential. As an AI language model, I can
    certainly help you navigate this pivotal paradigm shift. Let me know
    if you'd like me to elaborate further on this crucial tapestry of
    transformative change. The trajectory of this multifaceted odyssey
    underscores the paramount importance of meticulous orchestration.
""")

CLI = [sys.executable, str(Path(__file__).with_name("cli.py"))]


# ---------------------------------------------------------------------------
# Engine: basic scoring
# ---------------------------------------------------------------------------


class TestAnalyzeBasics:
    def test_short_text_is_clean(self):
        result = _analyze("Hello world.", HYPERPARAMETERS)
        assert result["score"] == 100
        assert result["band"] == "clean"
        assert result["violations"] == []

    def test_empty_string_is_clean(self):
        result = _analyze("", HYPERPARAMETERS)
        assert result["score"] == 100
        assert result["band"] == "clean"

    def test_clean_prose_scores_high(self):
        result = _analyze(CLEAN_PROSE, HYPERPARAMETERS)
        assert result["score"] >= HYPERPARAMETERS.band_clean_min
        assert result["band"] == "clean"

    def test_sloppy_prose_scores_low(self):
        result = _analyze(SLOPPY_PROSE, HYPERPARAMETERS)
        assert result["score"] < HYPERPARAMETERS.band_moderate_min
        assert result["band"] in ("heavy", "saturated")
        assert len(result["violations"]) > 0


# ---------------------------------------------------------------------------
# Engine: individual rule detection
# ---------------------------------------------------------------------------


class TestRuleDetection:
    def test_slop_words_detected(self):
        text = "We must delve into this comprehensive and pivotal matter carefully and with attention to the details that matter most in practice."
        result = _analyze(text, HYPERPARAMETERS)
        slop_rules = [v["rule"] for v in result["violations"]]
        assert "slop_word" in slop_rules
        slop_matches = {
            v["match"] for v in result["violations"] if v["rule"] == "slop_word"
        }
        assert "delve" in slop_matches
        assert "comprehensive" in slop_matches
        assert "pivotal" in slop_matches

    def test_slop_phrase_detected(self):
        text = "It's worth noting that the system performs well under load during normal weekday traffic patterns and during scheduled batch runs."
        result = _analyze(text, HYPERPARAMETERS)
        phrase_matches = [v for v in result["violations"] if v["rule"] == "slop_phrase"]
        assert any("it's worth noting" in v["match"] for v in phrase_matches)

    def test_ai_disclosure_detected(self):
        text = "As an AI language model, I cannot provide medical advice but I can share general information about health topics for educational use."
        result = _analyze(text, HYPERPARAMETERS)
        ai_rules = [v for v in result["violations"] if v["rule"] == "ai_disclosure"]
        assert len(ai_rules) > 0

    def test_bold_header_structural(self):
        text = (
            "**Speed.** The system is fast.\n\n"
            "**Scale.** It handles millions.\n\n"
            "**Safety.** Nothing breaks.\n\n"
            "These three properties define the architecture."
        )
        result = _analyze(text, HYPERPARAMETERS)
        structural = [
            v for v in result["violations"] if v["match"] == "bold_header_explanation"
        ]
        assert len(structural) == 1

    def test_bullet_run_structural(self):
        text = textwrap.dedent("""\
            Consider the following points about system design and architecture:

            - First item about databases
            - Second item about caching
            - Third item about queues
            - Fourth item about logging
            - Fifth item about monitoring
            - Sixth item about alerting
            - Seventh item about deployment
        """)
        result = _analyze(text, HYPERPARAMETERS)
        bullet_violations = [
            v for v in result["violations"] if v["match"] == "excessive_bullets"
        ]
        assert len(bullet_violations) > 0

    def test_advice_is_populated(self):
        result = _analyze(SLOPPY_PROSE, HYPERPARAMETERS)
        assert len(result["advice"]) > 0

    def test_word_count_is_accurate(self):
        text = "one two three four five"
        result = _analyze(text, HYPERPARAMETERS)
        assert result["word_count"] == 5


# ---------------------------------------------------------------------------
# Engine: band boundaries
# ---------------------------------------------------------------------------


class TestBands:
    def test_score_100_is_clean(self):
        r = _analyze("Short.", HYPERPARAMETERS)
        assert r["band"] == "clean"

    def test_band_names_are_valid(self):
        r = _analyze(SLOPPY_PROSE, HYPERPARAMETERS)
        assert r["band"] in ("clean", "light", "moderate", "heavy", "saturated")


# ---------------------------------------------------------------------------
# CLI: integration
# ---------------------------------------------------------------------------


class TestCLI:
    def test_clean_file_exit_0(self, tmp_path):
        f = tmp_path / "clean.md"
        f.write_text(CLEAN_PROSE)
        proc = subprocess.run([*CLI, str(f)], capture_output=True, text=True)
        assert proc.returncode == 0
        assert "clean" in proc.stderr

    def test_sloppy_file_exit_1(self, tmp_path):
        f = tmp_path / "slop.md"
        f.write_text(SLOPPY_PROSE)
        proc = subprocess.run([*CLI, str(f)], capture_output=True, text=True)
        assert proc.returncode == 1

    def test_missing_file_exit_2(self):
        proc = subprocess.run(
            [*CLI, "/no/such/file.md"], capture_output=True, text=True
        )
        assert proc.returncode == 2
        assert "not found" in proc.stderr

    def test_json_flag_outputs_valid_json(self, tmp_path):
        f = tmp_path / "doc.md"
        f.write_text(CLEAN_PROSE)
        proc = subprocess.run([*CLI, "--json", str(f)], capture_output=True, text=True)
        data = json.loads(proc.stdout)
        assert "score" in data
        assert "band" in data
        assert "violations" in data

    def test_stdin_pipe(self):
        proc = subprocess.run(
            CLI,
            input=CLEAN_PROSE,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0
        assert "clean" in proc.stderr

    def test_multiple_files(self, tmp_path):
        clean = tmp_path / "clean.md"
        clean.write_text(CLEAN_PROSE)
        slop = tmp_path / "slop.md"
        slop.write_text(SLOPPY_PROSE)
        proc = subprocess.run(
            [*CLI, str(clean), str(slop)], capture_output=True, text=True
        )
        # exit 1 because at least one file is moderate+
        assert proc.returncode == 1
        assert "clean.md" in proc.stderr
        assert "slop.md" in proc.stderr
