const PREVIEWS = {
  mcp: {
    label: "Agent / MCP",
    title: "Lint prose inside Codex or Claude",
    copy:
      "Add the server once, then call check_slop or check_slop_file whenever an agent drafts docs, release notes, or project updates.",
    code: [
      "codex mcp add slop-guard -- uvx slop-guard",
      "claude mcp add slop-guard -- uvx slop-guard",
      "",
      "# tools exposed by the server",
      "check_slop(text=\"Draft text here\")",
      "check_slop_file(file_path=\"docs/landing.md\")",
    ].join("\n"),
  },
  cli: {
    label: "CLI",
    title: "Score files, stdin, or inline text",
    copy:
      "Use sg for one-off checks while you edit copy. The format is compact enough for terminal work and detailed enough for real rewrites.",
    code: [
      "uvx --from slop-guard sg README.md",
      "uvx --from slop-guard sg \"This is a crucial paradigm shift.\"",
      "",
      "# after installation",
      "sg -v docs/landing.md",
      "sg -j report.md | jq '.score'",
    ].join("\n"),
  },
  ci: {
    label: "CI / Threshold",
    title: "Fail the build when the prose drops too far",
    copy:
      "Thresholds turn the score into a gate. If a docs change lands below the floor, the command exits 1 and the job fails.",
    code: [
      "# fail if any file scores below 60",
      "sg -t 60 docs/*.md",
      "",
      "# only print failing paths",
      "sg -q -t 60 **/*.md",
    ].join("\n"),
  },
  fit: {
    label: "Fit Rules",
    title: "Tune the rule config to your own corpus",
    copy:
      "Use sg-fit when you want the scoring to reflect a specific house style instead of the packaged defaults.",
    code: [
      "sg-fit data.jsonl rules.fitted.jsonl",
      "",
      "sg-fit --output rules.fitted.jsonl \\",
      "  positives/**/*.md \\",
      "  --negative-dataset negatives/**/*.md",
      "",
      "sg -c rules.fitted.jsonl docs/landing.md",
    ].join("\n"),
  },
};

const DEMOS = {
  slop: {
    caption: "Sample run with repeated stock words, stock phrases, and one density hit.",
    text:
      "This is a crucial and groundbreaking paradigm for modern teams. It's worth noting that we can leverage a robust framework to unlock outcomes. In conclusion, the key takeaway is simple: embrace the landscape and move forward.",
    score: 0,
    band: "saturated",
    scoreLine: "<text:1>: 0/100 [saturated] (36 words) !!!",
    countSummary: "8 slop words | 3 stock phrases | 1 colon-density hit",
    inspectorTitle: "Rule hits are visible and specific.",
    inspectorCopy:
      "Hover a highlight to inspect the exact rule name, penalty, and rewrite advice returned by the analyzer.",
    stats: [
      { value: "8", label: "slop words" },
      { value: "3", label: "stock phrases" },
      { value: "1", label: "colon-density hit" },
      { value: "36", label: "words" },
    ],
    detailEmpty: {
      rule: "Hover a marked span",
      advice: "The tooltip and this panel both use the same analyzer response.",
      context: "",
    },
    annotations: [
      {
        match: "crucial",
        kind: "word",
        rule: "slop_word",
        penalty: -2,
        advice: "Replace 'crucial' — what specifically do you mean?",
        context: "This is a crucial and groundbreaking paradi...",
      },
      {
        match: "groundbreaking",
        kind: "word",
        rule: "slop_word",
        penalty: -2,
        advice: "Replace 'groundbreaking' — what specifically do you mean?",
        context: "This is a crucial and groundbreaking paradigm for modern te...",
      },
      {
        match: "paradigm",
        kind: "word",
        rule: "slop_word",
        penalty: -2,
        advice: "Replace 'paradigm' — what specifically do you mean?",
        context: "...rucial and groundbreaking paradigm for modern teams. It's wo...",
      },
      {
        match: "It's worth noting",
        kind: "phrase",
        rule: "slop_phrase",
        penalty: -3,
        advice: "Cut 'it's worth noting' — just state the point directly.",
        context: "...igm for modern teams. It's worth noting that we can leverage...",
      },
      {
        match: "leverage",
        kind: "word",
        rule: "slop_word",
        penalty: -2,
        advice: "Replace 'leverage' — what specifically do you mean?",
        context: "... worth noting that we can leverage a robust framework to unl...",
      },
      {
        match: "robust",
        kind: "word",
        rule: "slop_word",
        penalty: -2,
        advice: "Replace 'robust' — what specifically do you mean?",
        context: "...ing that we can leverage a robust framework to unlock outcom...",
      },
      {
        match: "unlock",
        kind: "word",
        rule: "slop_word",
        penalty: -2,
        advice: "Replace 'unlock' — what specifically do you mean?",
        context: "...rage a robust framework to unlock outcomes. In conclusion, t...",
      },
      {
        match: "In conclusion",
        kind: "phrase",
        rule: "slop_phrase",
        penalty: -3,
        advice: "Cut 'in conclusion' — just state the point directly.",
        context: "...ork to unlock outcomes. In conclusion, the key takeaway is s...",
      },
      {
        match: "the key takeaway",
        kind: "phrase",
        rule: "slop_phrase",
        penalty: -3,
        advice: "Cut 'the key takeaway' — just state the point directly.",
        context: "...comes. In conclusion, the key takeaway is simple: embrace th...",
      },
      {
        match: "embrace",
        kind: "word",
        rule: "slop_word",
        penalty: -2,
        advice: "Replace 'embrace' — what specifically do you mean?",
        context: "...he key takeaway is simple: embrace the landscape and move fo...",
      },
      {
        match: "landscape",
        kind: "word",
        rule: "slop_word",
        penalty: -2,
        advice: "Replace 'landscape' — what specifically do you mean?",
        context: "...ay is simple: embrace the landscape and move forward.",
      },
    ],
  },
  clean: {
    caption: "The same analyzer on a rewrite with direct claims and no hits.",
    text:
      "The tool flags stock phrases, inflated adjectives, and repeated templates in prose. It returns a score, the matched spans, and direct advice so you can rewrite the draft with specific claims.",
    score: 100,
    band: "clean",
    scoreLine: "<text:1>: 100/100 [clean] (31 words) .",
    countSummary: "0 active rule counts",
    inspectorTitle: "No violations in this pass.",
    inspectorCopy:
      "The output becomes a clean score with an empty violation list and no advice items to resolve.",
    stats: [
      { value: "0", label: "violations" },
      { value: "0", label: "advice items" },
      { value: "31", label: "words" },
      { value: "100", label: "score" },
    ],
    detailEmpty: {
      rule: "No active matches",
      advice: "This rewrite cleared the rule set used for the sample run.",
      context: "The payload is just the score, band, word count, and empty violation and advice lists.",
    },
    annotations: [],
  },
};

const BAND_COLORS = {
  clean: "var(--clean)",
  light: "var(--accent)",
  moderate: "#c9832d",
  heavy: "var(--slop)",
  saturated: "var(--slop)",
};

function formatRule(rule) {
  return rule.replaceAll("_", " ");
}

function buildTooltipContent(annotation) {
  const wrapper = document.createElement("span");
  wrapper.className = "annotation-tooltip";

  const label = document.createElement("strong");
  label.textContent = `${formatRule(annotation.rule)} | ${annotation.penalty}`;
  wrapper.appendChild(label);

  const advice = document.createElement("span");
  advice.textContent = annotation.advice;
  wrapper.appendChild(advice);

  return wrapper;
}

function locateAnnotations(example) {
  const lowerText = example.text.toLowerCase();
  let cursor = 0;

  return example.annotations
    .map((annotation) => {
      const matchLower = annotation.match.toLowerCase();
      let start = lowerText.indexOf(matchLower, cursor);
      if (start < 0) {
        start = lowerText.indexOf(matchLower);
      }
      if (start < 0) {
        return null;
      }
      const end = start + annotation.match.length;
      cursor = end;
      return { ...annotation, start, end };
    })
    .filter(Boolean)
    .sort((left, right) => left.start - right.start);
}

function setDetail(detailNodes, annotation) {
  detailNodes.rule.textContent = `${formatRule(annotation.rule)} (${annotation.penalty})`;
  detailNodes.advice.textContent = annotation.advice;
  detailNodes.context.textContent = annotation.context;
}

function setEmptyDetail(detailNodes, emptyState) {
  detailNodes.rule.textContent = emptyState.rule;
  detailNodes.advice.textContent = emptyState.advice;
  detailNodes.context.textContent = emptyState.context;
}

function renderStats(statGrid, stats) {
  statGrid.replaceChildren();
  stats.forEach((stat) => {
    const card = document.createElement("div");
    card.className = "stat-card";

    const value = document.createElement("strong");
    value.textContent = stat.value;
    card.appendChild(value);

    const label = document.createElement("span");
    label.textContent = stat.label;
    card.appendChild(label);

    statGrid.appendChild(card);
  });
}

function renderAnnotatedText(copyNode, example, detailNodes) {
  copyNode.replaceChildren();
  const located = locateAnnotations(example);

  if (!located.length) {
    copyNode.textContent = example.text;
    setEmptyDetail(detailNodes, example.detailEmpty);
    return;
  }

  let activeMark = null;
  let cursor = 0;

  const setActiveMark = (mark, annotation) => {
    if (activeMark && activeMark !== mark) {
      activeMark.classList.remove("is-selected");
    }
    activeMark = mark;
    activeMark.classList.add("is-selected");
    setDetail(detailNodes, annotation);
  };

  located.forEach((annotation) => {
    if (annotation.start > cursor) {
      copyNode.appendChild(document.createTextNode(example.text.slice(cursor, annotation.start)));
    }

    const mark = document.createElement("span");
    mark.className = `annotation annotation--${annotation.kind}`;
    mark.tabIndex = 0;
    mark.textContent = example.text.slice(annotation.start, annotation.end);
    mark.appendChild(buildTooltipContent(annotation));

    mark.addEventListener("mouseenter", () => setActiveMark(mark, annotation));
    mark.addEventListener("focus", () => setActiveMark(mark, annotation));
    mark.addEventListener("click", () => setActiveMark(mark, annotation));

    copyNode.appendChild(mark);
    cursor = annotation.end;

    if (!activeMark) {
      setActiveMark(mark, annotation);
    }
  });

  if (cursor < example.text.length) {
    copyNode.appendChild(document.createTextNode(example.text.slice(cursor)));
  }
}

function initDemo() {
  const buttons = Array.from(document.querySelectorAll("[data-mode-button]"));
  const copyNode = document.querySelector("[data-annotated-copy]");
  const captionNode = document.querySelector("[data-demo-caption]");
  const scoreLineNode = document.querySelector("[data-score-line]");
  const countSummaryNode = document.querySelector("[data-count-summary]");
  const scoreValueNode = document.querySelector("[data-score-value]");
  const scoreBandNode = document.querySelector("[data-score-band]");
  const scoreRingNode = document.querySelector("[data-score-ring]");
  const inspectorTitleNode = document.querySelector("[data-inspector-title]");
  const inspectorCopyNode = document.querySelector("[data-inspector-copy]");
  const statGridNode = document.querySelector("[data-stat-grid]");

  const detailNodes = {
    rule: document.querySelector("[data-detail-rule]"),
    advice: document.querySelector("[data-detail-advice]"),
    context: document.querySelector("[data-detail-context]"),
  };

  const renderMode = (mode) => {
    const example = DEMOS[mode];
    buttons.forEach((button) => {
      const isActive = button.dataset.modeButton === mode;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-pressed", String(isActive));
    });

    captionNode.textContent = example.caption;
    scoreLineNode.textContent = example.scoreLine;
    countSummaryNode.textContent = example.countSummary;
    scoreValueNode.textContent = String(example.score);
    scoreBandNode.textContent = example.band;
    inspectorTitleNode.textContent = example.inspectorTitle;
    inspectorCopyNode.textContent = example.inspectorCopy;
    scoreRingNode.style.setProperty("--progress", String(example.score));
    scoreRingNode.style.setProperty("--ring-color", BAND_COLORS[example.band]);

    renderStats(statGridNode, example.stats);
    renderAnnotatedText(copyNode, example, detailNodes);
  };

  buttons.forEach((button) => {
    button.addEventListener("click", () => renderMode(button.dataset.modeButton));
  });

  renderMode("slop");
}

function initUsagePreview() {
  const steps = Array.from(document.querySelectorAll(".usage-step[data-preview-key]"));
  const labelNode = document.querySelector("[data-preview-label]");
  const titleNode = document.querySelector("[data-preview-title]");
  const copyNode = document.querySelector("[data-preview-copy]");
  const codeNode = document.querySelector("[data-preview-code]");

  const renderPreview = (key) => {
    const preview = PREVIEWS[key];
    if (!preview) {
      return;
    }

    labelNode.textContent = preview.label;
    titleNode.textContent = preview.title;
    copyNode.textContent = preview.copy;
    codeNode.textContent = preview.code;

    steps.forEach((step) => {
      step.classList.toggle("is-active", step.dataset.previewKey === key);
    });
  };

  steps.forEach((step) => {
    step.addEventListener("mouseenter", () => renderPreview(step.dataset.previewKey));
    step.addEventListener("focusin", () => renderPreview(step.dataset.previewKey));
  });

  if (!("IntersectionObserver" in window)) {
    renderPreview(steps[0]?.dataset.previewKey || "mcp");
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];
      if (visible) {
        renderPreview(visible.target.dataset.previewKey);
      }
    },
    {
      threshold: [0.35, 0.6, 0.85],
      rootMargin: "-10% 0px -18% 0px",
    },
  );

  steps.forEach((step) => observer.observe(step));
  renderPreview(steps[0]?.dataset.previewKey || "mcp");
}

function initCopyButtons() {
  const buttons = Array.from(document.querySelectorAll(".copy-button[data-copy-text]"));
  if (!buttons.length) {
    return;
  }

  const copyText = async (text) => {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }

    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "absolute";
    area.style.left = "-9999px";
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    document.body.removeChild(area);
  };

  buttons.forEach((button) => {
    const defaultLabel = button.getAttribute("aria-label") || "Copy command";

    button.addEventListener("click", async () => {
      try {
        await copyText(button.dataset.copyText || "");
        button.classList.add("is-copied");
        button.setAttribute("aria-label", "Copied");
        window.setTimeout(() => {
          button.classList.remove("is-copied");
          button.setAttribute("aria-label", defaultLabel);
        }, 1200);
      } catch (_error) {
        button.setAttribute("aria-label", "Copy failed");
        window.setTimeout(() => {
          button.setAttribute("aria-label", defaultLabel);
        }, 1200);
      }
    });
  });
}

function initReveals() {
  const nodes = Array.from(document.querySelectorAll(".reveal"));
  if (!nodes.length) {
    return;
  }

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || !("IntersectionObserver" in window)) {
    nodes.forEach((node) => node.classList.add("is-visible"));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    {
      threshold: 0.2,
      rootMargin: "0px 0px -8% 0px",
    },
  );

  nodes.forEach((node) => observer.observe(node));
}

document.addEventListener("DOMContentLoaded", () => {
  initReveals();
  initUsagePreview();
  initDemo();
  initCopyButtons();
});
