document.documentElement.classList.add("js-enabled");

const biteSwipeHeadlines = [
  "Tonight's pick does not need a group-chat spiral.",
  "Cravings, filters, and one cleaner shortlist.",
  "Find the campus bite that actually fits the plan.",
  "Swipe the maybes. Save the place.",
  "Fast food decisions for busy students.",
  "A better way to answer where should we eat.",
  "Match the meal to the moment.",
  "Turn nearby options into a real plan.",
  "Less scrolling. More eating.",
  "Budget, distance, cravings, and safety in one deck.",
  "Build a board before the hunger gets loud.",
  "Your next study-break spot is probably nearby.",
  "Make restaurant picking feel lighter.",
  "A smarter shortlist for friends, dates, and solo bites.",
  "Filter first, swipe second, eat sooner.",
  "Restaurant discovery built around how students decide.",
];

function setRandomBiteSwipeHeadline() {
  const headline = document.querySelector("[data-biteswipe-headline]");

  if (!headline || biteSwipeHeadlines.length === 0) {
    return;
  }

  const index = Math.floor(Math.random() * biteSwipeHeadlines.length);
  headline.textContent = biteSwipeHeadlines[index];
  headline.dataset.loaded = "true";
}

function markSubmitting(form) {
  form.classList.add("is-submitting");
  const submitter = form.querySelector("button[type='submit'], input[type='submit']");
  if (submitter) {
    submitter.dataset.originalText = submitter.value || submitter.textContent;
    if (submitter.tagName === "INPUT") {
      submitter.value = "Working...";
    } else {
      submitter.textContent = "Working...";
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  setRandomBiteSwipeHeadline();

  document.querySelectorAll("a[target='_blank']").forEach((link) => {
    const rel = new Set((link.getAttribute("rel") || "").split(/\s+/).filter(Boolean));
    rel.add("noopener");
    rel.add("noreferrer");
    link.setAttribute("rel", Array.from(rel).join(" "));
  });

  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", () => {
      if (!form.matches("[data-keep-active]") && !form.classList.contains("interest-chip")) {
        markSubmitting(form);
      }
    });
  });
});
