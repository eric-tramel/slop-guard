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
      'check_slop(text="Draft text here")',
      'check_slop_file(file_path="docs/landing.md")',
    ].join("\n"),
  },
  cli: {
    label: "CLI",
    title: "Score files, stdin, or inline text",
    copy:
      "Use sg for one-off checks while you edit copy. The format is compact enough for terminal work and detailed enough for real rewrites.",
    code: [
      "uvx --from slop-guard sg README.md",
      'uvx --from slop-guard sg "This is a crucial paradigm shift."',
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

const EXCERPTS = [
  {
    key: "pure_habits",
    dataset: "Pure slop dataset",
    title: "Habit-building advice",
    shortLabel: "Habits",
    text: `Building consistency with simple, healthy habits starts with a single, clear intention: treat each habit like a tiny, repeatable tool you reach for every day. Instead of trying to overhaul your entire lifestyle at once, pick one behavior that feels almost effortless— a five-minute stretch after waking, a glass of water before each meal, or a ten-minute walk after dinner. When the action is low-stakes and clearly defined, your brain treats it as a familiar cue rather than a daunting challenge, making it far easier to repeat without fatigue or guilt.`,
    score: 7,
    band: "saturated",
    wordCount: 90,
    counts: {
      em_dash: 1,
      colon_density: 1,
    },
    violations: [
      {
        rule: "em_dash",
        match: "em_dash_density",
        context: "1 em dashes in 90 words (1.7 per 150 words)",
        penalty: -3,
      },
      {
        rule: "colon_density",
        match: "colon_density",
        context: "1 elaboration colons in 90 words (1.7 per 150 words)",
        penalty: -3,
      },
    ],
    advice: [
      "Too many em dashes (1 in 90 words) — use other punctuation.",
      "Too many elaboration colons (1 in 90 words) — use periods or restructure sentences.",
    ],
  },
  {
    key: "pure_brand",
    dataset: "Pure slop dataset",
    title: "Personal brand playbook",
    shortLabel: "Brand",
    text: [
      `Building a personal brand at work isn’t about self-promotion for the sake of limelight—it’s about deliberately shaping how colleagues and leaders perceive the unique blend of skills, values, and personality you bring to the table. Start by clarifying your “brand statement”: a concise sentence that captures what you stand for (e.g., “I turn complex data into clear, actionable strategy”) and the strengths you consistently demonstrate. Write it down, rehearse it, and weave it into everyday interactions—whether you’re presenting a report, volunteering for a cross-team project, or simply chatting during coffee breaks. This clarity gives you a north star and makes it easier for others to remember and reference you when opportunities arise.`,
      `Next, amplify that brand through consistent, intentional actions. Publicly share your expertise by speaking up in meetings, authoring short how-to guides, or mentoring newer teammates—each interaction is a chance to reinforce your core message. Pair visibility with credibility: follow through on commitments, meet deadlines, and be the person who solves problems rather than merely points out them. Over time, patterns emerge (e.g., “the go-to person for risk mitigation” or “the champion of sustainable practices”), cementing your reputation as someone who delivers on specific, valuable promises.`,
    ].join("\n\n"),
    score: 16,
    band: "saturated",
    wordCount: 197,
    counts: {
      slop_words: 1,
      structural: 1,
      em_dash: 1,
      colon_density: 1,
    },
    violations: [
      {
        rule: "slop_word",
        match: "actionable",
        context: "...complex data into clear, actionable strategy”) and the stren...",
        penalty: -2,
      },
      {
        rule: "structural",
        match: "triadic",
        context: "...nique blend of skills, values, and personality you bring to ...",
        penalty: -1,
      },
      {
        rule: "em_dash",
        match: "em_dash_density",
        context: "3 em dashes in 197 words (2.3 per 150 words)",
        penalty: -3,
      },
      {
        rule: "colon_density",
        match: "colon_density",
        context: "2 elaboration colons in 197 words (1.5 per 150 words)",
        penalty: -3,
      },
    ],
    advice: [
      "Replace 'actionable' — what specifically do you mean?",
      "Too many em dashes (3 in 197 words) — use other punctuation.",
      "Too many elaboration colons (2 in 197 words) — use periods or restructure sentences.",
    ],
  },
  {
    key: "pure_hybrid",
    dataset: "Pure slop dataset",
    title: "Hybrid work guidance",
    shortLabel: "Hybrid",
    text: [
      `Hybrid work is no longer a temporary fix; it’s the new normal, and the teams that thrive are those that treat collaboration as a deliberate skill rather than a default setting. The first step to navigating hybrid collaboration with confidence is to establish crystal-clear expectations up front. When everyone—whether they’re logging in from a home office, a coworking space, or the office floor—knows the preferred channels for updates, the expected response windows, and the standards for participation, ambiguity evaporates. A quick kickoff meeting that outlines these norms, paired with a living document that captures them, turns a patchwork of ad-hoc practices into a shared roadmap that everyone can reference and trust.`,
      `Second, intentionality beats spontaneity. In a hybrid environment, the moments when colleagues cross paths organically are fewer, so you must schedule them deliberately. Reserve dedicated “sync-up” windows for brainstorming, decision-making, and relationship-building, and treat them as non-negotiable calendar events. Use video for those high-touch interactions, but don’t shy away from asynchronous tools—shared whiteboards, threaded discussions, and concise written recaps—when time zones or workloads make simultaneous presence impractical. By allocating specific slots for both real-time and async collaboration, you guarantee that every voice has a chance to be heard, heard, and acted upon.`,
    ].join("\n\n"),
    score: 45,
    band: "moderate",
    wordCount: 203,
    counts: {
      structural: 1,
      em_dash: 1,
    },
    violations: [
      {
        rule: "structural",
        match: "triadic",
        context: "...has a chance to be heard, heard, and acted upon.",
        penalty: -1,
      },
      {
        rule: "em_dash",
        match: "em_dash_density",
        context: "4 em dashes in 203 words (3.0 per 150 words)",
        penalty: -3,
      },
    ],
    advice: [
      "Too many em dashes (4 in 203 words) — use other punctuation.",
    ],
  },
  {
    key: "true_clean_code",
    dataset: "True text corpus",
    title: "Goodbye, Clean Code",
    shortLabel: "Clean Code",
    text: `Goodbye, Clean Code January 11, 2020 It was a late evening.\n\nMy colleague has just checked in the code that they’ve been writing all week. We were working on a graphics editor canvas, and they implemented the ability to resize shapes like rectangles and ovals by dragging small handles at their edges.`,
    score: 100,
    band: "clean",
    wordCount: 52,
    counts: {},
    violations: [],
    advice: [],
  },
  {
    key: "true_comments",
    dataset: "True text corpus",
    title: "Code tells you how",
    shortLabel: "Comments",
    text: [
      `In an earlier post on the philosophy of code comments, I noted that the best kind of comments are the ones you don’t need. Allow me to clarify that point. You should first strive to make your code as simple as possible to understand without relying on comments as a crutch. Only at the point where the code cannot be made easier to understand should you begin to add comments.`,
      `It helps to keep your audience in mind when you’re writing code. The classic book Structure and Interpretation of Computer Programs, originally published in 1985, gets right to the point in the preface: Programs must be written for people to read, and only incidentally for machines to execute.`,
    ].join("\n\n"),
    score: 100,
    band: "clean",
    wordCount: 118,
    counts: {},
    violations: [],
    advice: [],
  },
];

const BAND_COLORS = {
  clean: "var(--clean)",
  light: "var(--accent)",
  moderate: "#c9832d",
  heavy: "var(--slop)",
  saturated: "var(--slop)",
};

const COUNT_LABELS = {
  slop_words: "slop words",
  structural: "structural hits",
  em_dash: "em-dash hits",
  colon_density: "colon hits",
  contrast_pairs: "contrast pairs",
};

function formatRule(rule) {
  return rule.replaceAll("_", " ");
}

function formatCountKey(key) {
  return COUNT_LABELS[key] || formatRule(key);
}

function buildScoreLine(sample) {
  return `${sample.dataset}: ${sample.score}/100 [${sample.band}] (${sample.wordCount} words)`;
}

function buildCountSummary(sample) {
  const active = Object.entries(sample.counts);
  if (!active.length) {
    return "No active rule counts";
  }
  return active.map(([key, value]) => `${value} ${formatCountKey(key)}`).join(" | ");
}

function buildStats(sample) {
  const active = Object.entries(sample.counts).map(([key, value]) => ({
    value: String(value),
    label: formatCountKey(key),
  }));

  if (!active.length) {
    return [
      { value: "0", label: "active rules" },
      { value: String(sample.advice.length), label: "advice items" },
      { value: String(sample.wordCount), label: "words" },
      { value: String(sample.score), label: "score" },
    ];
  }

  return [...active.slice(0, 3), { value: String(sample.wordCount), label: "words" }].slice(0, 4);
}

function deriveAdvice(sample, violation) {
  if (violation.rule === "slop_word") {
    return `Replace '${violation.match}' — what specifically do you mean?`;
  }

  if (violation.rule === "contrast_pair") {
    return `‘${violation.match}’ — 'X, not Y' contrast — consider rephrasing to avoid the Claude pattern.`;
  }

  if (violation.rule === "em_dash") {
    return sample.advice.find((item) => item.includes("em dashes")) || "Too many em dashes in this excerpt.";
  }

  if (violation.rule === "colon_density") {
    return sample.advice.find((item) => item.includes("elaboration colons")) || "Too many elaboration colons in this excerpt.";
  }

  if (violation.rule === "structural") {
    return "A structural pattern in this sentence contributes to the score.";
  }

  return sample.advice[0] || "Inspect this span in context.";
}

function locateLiteralSpan(text, match, cursorMap) {
  const lowerText = text.toLowerCase();
  const lowerMatch = match.toLowerCase();
  let cursor = cursorMap.get(lowerMatch) ?? 0;
  let start = lowerText.indexOf(lowerMatch, cursor);

  if (start < 0) {
    start = lowerText.indexOf(lowerMatch);
  }
  if (start < 0) {
    return [];
  }

  cursorMap.set(lowerMatch, start + match.length);
  return [{ start, end: start + match.length }];
}

function locateTriadicSpans(text) {
  const spans = [];
  const triadicPattern = /\b[^,.;:\n]{2,40},\s+[^,.;:\n]{2,40},\s+and\s+[^,.;:\n]{2,40}\b/gu;
  for (const match of text.matchAll(triadicPattern)) {
    spans.push({ start: match.index, end: match.index + match[0].length });
  }
  return spans;
}

function locateCharacterSpans(text, pattern) {
  const spans = [];
  for (const match of text.matchAll(pattern)) {
    spans.push({ start: match.index, end: match.index + match[0].length });
  }
  return spans;
}

function locateViolationSpans(text, violation, cursorMap) {
  if (violation.rule === "em_dash") {
    return locateCharacterSpans(text, /[—]/gu);
  }

  if (violation.rule === "colon_density") {
    return locateCharacterSpans(text, /:/gu);
  }

  if (violation.rule === "structural" && violation.match === "triadic") {
    return locateTriadicSpans(text);
  }

  return locateLiteralSpan(text, violation.match, cursorMap);
}

function buildAnnotationInstances(sample) {
  const cursorMap = new Map();
  const annotations = [];

  sample.violations.forEach((violation, violationIndex) => {
    const spans = locateViolationSpans(sample.text, violation, cursorMap);
    spans.forEach((span, spanIndex) => {
      annotations.push({
        id: `${sample.key}:${violationIndex}:${spanIndex}`,
        ...violation,
        advice: deriveAdvice(sample, violation),
        start: span.start,
        end: span.end,
      });
    });
  });

  return annotations.sort((left, right) => left.start - right.start || left.end - right.end);
}

function buildHighlightMap(text, annotations) {
  const map = Array.from({ length: text.length }, () => []);
  annotations.forEach((annotation) => {
    for (let index = annotation.start; index < annotation.end; index += 1) {
      map[index].push(annotation);
    }
  });
  return map;
}

function annotationAlpha(score, hitCount) {
  const scoreWeight = (100 - score) / 100;
  const base = 0.08 + scoreWeight * 0.24;
  return Math.min(0.58, base + (hitCount - 1) * 0.09);
}

function buildTooltipContent(hits) {
  const tooltip = document.createElement("span");
  tooltip.className = "annotation-tooltip";

  const label = document.createElement("strong");
  label.textContent =
    hits.length === 1 ? `${formatRule(hits[0].rule)} | ${hits[0].penalty}` : `${hits.length} lint hits`;
  tooltip.appendChild(label);

  const body = document.createElement("span");
  if (hits.length === 1) {
    body.textContent = hits[0].advice;
  } else {
    body.textContent = hits
      .slice(0, 2)
      .map((hit) => `${formatRule(hit.rule)}: ${hit.advice}`)
      .join(" ");
  }
  tooltip.appendChild(body);

  return tooltip;
}

function setDetailBody(detailNode, hits, sample) {
  detailNode.replaceChildren();

  if (!hits.length) {
    const title = document.createElement("h4");
    title.textContent = "No active lint hits";
    detailNode.appendChild(title);

    const advice = document.createElement("p");
    advice.className = "detail-card__advice";
    advice.textContent =
      sample.score === 100
        ? "This excerpt passed clean with no returned violations."
        : "Move the slider or hover a highlighted span to inspect a lint hit.";
    detailNode.appendChild(advice);

    const context = document.createElement("p");
    context.className = "detail-card__context";
    context.textContent = `${sample.dataset} · ${sample.title}`;
    detailNode.appendChild(context);
    return;
  }

  const title = document.createElement("h4");
  title.textContent =
    hits.length === 1 ? `${formatRule(hits[0].rule)} (${hits[0].penalty})` : `${hits.length} overlapping lint hits`;
  detailNode.appendChild(title);

  if (hits.length === 1) {
    const advice = document.createElement("p");
    advice.className = "detail-card__advice";
    advice.textContent = hits[0].advice;
    detailNode.appendChild(advice);

    const context = document.createElement("p");
    context.className = "detail-card__context";
    context.textContent = hits[0].context;
    detailNode.appendChild(context);
    return;
  }

  const list = document.createElement("ul");
  list.className = "detail-card__list";

  hits.forEach((hit) => {
    const item = document.createElement("li");
    const itemTitle = document.createElement("strong");
    itemTitle.textContent = formatRule(hit.rule);
    item.appendChild(itemTitle);

    const itemAdvice = document.createElement("span");
    itemAdvice.textContent = hit.advice;
    item.appendChild(itemAdvice);

    list.appendChild(item);
  });

  detailNode.appendChild(list);
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

function renderAnnotatedText(copyNode, sample, detailNode) {
  copyNode.replaceChildren();
  copyNode.style.setProperty("--sample-wash", ((100 - sample.score) / 100).toFixed(2));

  const annotations = buildAnnotationInstances(sample);
  const highlightMap = buildHighlightMap(sample.text, annotations);
  let activeMark = null;
  let firstHighlightedMark = null;

  const setActiveMark = (mark, hits) => {
    if (activeMark && activeMark !== mark) {
      activeMark.classList.remove("is-selected");
    }
    activeMark = mark;
    activeMark.classList.add("is-selected");
    setDetailBody(detailNode, hits, sample);
  };

  const paragraphs = sample.text.split("\n\n");
  let globalOffset = 0;

  paragraphs.forEach((paragraph) => {
    const paragraphNode = document.createElement("p");
    let localIndex = 0;

    while (localIndex < paragraph.length) {
      const absoluteIndex = globalOffset + localIndex;
      const hits = highlightMap[absoluteIndex];
      const signature = hits.map((hit) => hit.id).join("|");
      let sliceEnd = localIndex + 1;

      while (sliceEnd < paragraph.length) {
        const nextHits = highlightMap[globalOffset + sliceEnd];
        const nextSignature = nextHits.map((hit) => hit.id).join("|");
        if (nextSignature !== signature) {
          break;
        }
        sliceEnd += 1;
      }

      const chunk = paragraph.slice(localIndex, sliceEnd);
      if (!hits.length) {
        paragraphNode.appendChild(document.createTextNode(chunk));
      } else {
        const mark = document.createElement("span");
        mark.className = "annotation";
        mark.tabIndex = 0;
        mark.style.setProperty("--annotation-alpha", annotationAlpha(sample.score, hits.length).toFixed(2));
        mark.style.setProperty(
          "--annotation-depth",
          Math.min(0.7, annotationAlpha(sample.score, hits.length) + 0.12).toFixed(2),
        );
        if (hits.length > 1) {
          mark.classList.add("annotation--stacked");
        }
        mark.textContent = chunk;
        mark.appendChild(buildTooltipContent(hits));

        mark.addEventListener("mouseenter", () => setActiveMark(mark, hits));
        mark.addEventListener("focus", () => setActiveMark(mark, hits));
        mark.addEventListener("click", () => setActiveMark(mark, hits));

        if (!firstHighlightedMark) {
          firstHighlightedMark = mark;
        }

        paragraphNode.appendChild(mark);
      }

      localIndex = sliceEnd;
    }

    copyNode.appendChild(paragraphNode);
    globalOffset += paragraph.length + 2;
  });

  if (firstHighlightedMark) {
    const firstHits = highlightMap.find((hits) => hits.length);
    setActiveMark(firstHighlightedMark, firstHits || []);
  } else {
    setDetailBody(detailNode, [], sample);
  }
}

function initDemo() {
  const slider = document.querySelector("[data-example-slider]");
  const stepContainer = document.querySelector("[data-slider-steps]");
  const sampleTitleNode = document.querySelector("[data-sample-title]");
  const captionNode = document.querySelector("[data-demo-caption]");
  const copyNode = document.querySelector("[data-annotated-copy]");
  const scoreLineNode = document.querySelector("[data-score-line]");
  const countSummaryNode = document.querySelector("[data-count-summary]");
  const scoreValueNode = document.querySelector("[data-score-value]");
  const scoreBandNode = document.querySelector("[data-score-band]");
  const scoreRingNode = document.querySelector("[data-score-ring]");
  const inspectorTitleNode = document.querySelector("[data-inspector-title]");
  const inspectorCopyNode = document.querySelector("[data-inspector-copy]");
  const statGridNode = document.querySelector("[data-stat-grid]");
  const detailNode = document.querySelector("[data-detail-body]");

  if (!slider || !stepContainer) {
    return;
  }

  slider.max = String(EXCERPTS.length - 1);

  const renderSample = (index) => {
    const sample = EXCERPTS[index];
    sampleTitleNode.textContent = sample.title;
    captionNode.textContent = `${sample.dataset} · ${sample.score}/100 · ${sample.band}`;
    scoreLineNode.textContent = buildScoreLine(sample);
    countSummaryNode.textContent = buildCountSummary(sample);
    scoreValueNode.textContent = String(sample.score);
    scoreBandNode.textContent = sample.band;
    inspectorTitleNode.textContent = sample.title;
    inspectorCopyNode.textContent = `${sample.dataset}. Hover a highlighted span to inspect the lint payload.`;
    scoreRingNode.style.setProperty("--progress", String(sample.score));
    scoreRingNode.style.setProperty("--ring-color", BAND_COLORS[sample.band]);

    renderStats(statGridNode, buildStats(sample));
    renderAnnotatedText(copyNode, sample, detailNode);

    Array.from(stepContainer.querySelectorAll("button")).forEach((button, buttonIndex) => {
      const isActive = buttonIndex === index;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-pressed", String(isActive));
    });
  };

  EXCERPTS.forEach((sample, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "slider-step";
    button.textContent = sample.shortLabel;
    button.setAttribute("aria-pressed", "false");
    button.addEventListener("click", () => {
      slider.value = String(index);
      renderSample(index);
    });
    stepContainer.appendChild(button);
  });

  slider.addEventListener("input", () => {
    renderSample(Number(slider.value));
  });

  renderSample(0);
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
