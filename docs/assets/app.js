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

function initUsagePreview() {
  const steps = Array.from(document.querySelectorAll(".usage-step[data-preview-key]"));
  const labelNode = document.querySelector("[data-preview-label]");
  const titleNode = document.querySelector("[data-preview-title]");
  const copyNode = document.querySelector("[data-preview-copy]");
  const codeNode = document.querySelector("[data-preview-code]");

  if (!steps.length || !labelNode || !titleNode || !copyNode || !codeNode) {
    return;
  }

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
  initCopyButtons();
});
