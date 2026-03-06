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

function initFeatureMeters() {
  const cards = Array.from(document.querySelectorAll(".feature-card--score"));
  if (!cards.length) {
    return;
  }

  cards.forEach((card) => {
    const marker = card.querySelector(".feature-meter__marker");
    if (!marker) {
      return;
    }

    const restingValue = marker.dataset.rest || marker.textContent || "";
    const activeValue = marker.dataset.active || restingValue;

    const setValue = (isActive) => {
      marker.textContent = isActive ? activeValue : restingValue;
    };

    card.addEventListener("mouseenter", () => setValue(true));
    card.addEventListener("mouseleave", () => setValue(false));
    card.addEventListener("focusin", () => setValue(true));
    card.addEventListener("focusout", (event) => {
      if (!card.contains(event.relatedTarget)) {
        setValue(false);
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
  initCopyButtons();
  initFeatureMeters();
});
