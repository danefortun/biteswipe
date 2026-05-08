const biteSwipeHeadlines = [
  { type: "text", value: "Tonight's pick does not need a group-chat spiral" },
  { type: "text", value: "Cravings, filters, and one cleaner shortlist" },
  { type: "text", value: "Find the campus bite that actually fits the plan" },
  { type: "text", value: "Swipe the maybes. Save the place" },
  { type: "text", value: "Fast food decisions for busy students" },
  { type: "text", value: "A better way to answer where should we eat" },
  { type: "text", value: "Match the meal to the moment" },
  { type: "text", value: "Originally created as a social media app 'LifeSwipe!'" },
  { type: "text", value: "Shoutout Dottie at Chick Fil A" },
  { type: "text", value: "Speed I'm watching your swipes, why you trying not to laugh" },
  { type: "text", value: "Get the allergens out of my swipes, I'm playing Minecraft!" },
  { type: "text", value: "Halal food is underrated" },
  { type: "text", value: "I stole this banner idea from Minecraft" },
  { type: "text", value: "Did you know one of the founders has Celiacs?" },
  { type: "text", value: "Restaurant discovery built around how students decide" },
  { type: "text", value: "Filter first, swipe second, eat sooner" },
  { type: "text", value: "A smarter shortlist for friends, dates, and solo bites" },
  { type: "text", value: "Make restaurant picking feel lighter" },
  { type: "text", value: "Your next study-break spot is probably nearby" },
  { type: "text", value: "This app's logo was based off Fizz" },
  { type: "text", value: "Budget, distance, cravings, and safety in one deck" },
  { type: "text", value: "guess what" },
  { type: "text", value: "chicken butt!" },
  { type: "text", value: "Donde esta la bibloteca" },
  { type: "text", value: "slowsilver03, say it till im dead huh" },
  { type: "text", value: "Less scrolling. More eating" },
  { type: "text", value: "Turn nearby options into a real plan" },
  {
    type: "image",
    src: "/static/ishowspeed-try-not-to-laugh.gif",
    alt: "BiteSwipe"
  }
];

function normalizeHeadline(item) {
  if (typeof item === "string") {
    return { type: "text", value: item };
  }

  if (!item || typeof item !== "object") {
    return { type: "text", value: "" };
  }

  if (item.type === "image") {
    return {
      type: "image",
      src: item.src || "/static/biteswipe.png",
      alt: item.alt || "BiteSwipe"
    };
  }

  return {
    type: "text",
    value: item.value || ""
  };
}

function shuffleHeadlines(values) {
  const shuffled = values.map(normalizeHeadline);

  for (let index = shuffled.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [shuffled[index], shuffled[swapIndex]] = [shuffled[swapIndex], shuffled[index]];
  }

  return shuffled;
}

function getNextBiteSwipeHeadline() {
  if (biteSwipeHeadlines.length === 0) return null;

  try {
    const queueKey = "biteswipe.headlineQueue.v3";
    const rawQueue = localStorage.getItem(queueKey);
    let queue = rawQueue ? JSON.parse(rawQueue).map(normalizeHeadline) : [];

    if (!Array.isArray(queue) || queue.length === 0) {
      queue = shuffleHeadlines(biteSwipeHeadlines);
    }

    const nextHeadline = normalizeHeadline(queue.shift());
    localStorage.setItem(queueKey, JSON.stringify(queue));

    return nextHeadline;
  } catch {
    const randomIndex = Math.floor(Math.random() * biteSwipeHeadlines.length);
    return normalizeHeadline(biteSwipeHeadlines[randomIndex]);
  }
}

function renderBiteSwipeHeadline(headline, item) {
  const normalized = normalizeHeadline(item);
  headline.textContent = "";

  if (normalized.type === "image") {
    const img = document.createElement("img");
    img.src = normalized.src;
    img.alt = normalized.alt;
    img.className = "header-headline-image";
    headline.appendChild(img);
    return;
  }

  headline.textContent = normalized.value;
}

function setRandomBiteSwipeHeadline() {
  const headlines = document.querySelectorAll("[data-biteswipe-headline]");
  const nextHeadline = getNextBiteSwipeHeadline();

  headlines.forEach((headline) => {
    renderBiteSwipeHeadline(headline, nextHeadline);
    headline.dataset.loaded = "true";
  });
}

document.addEventListener("DOMContentLoaded", () => {
  localStorage.removeItem("biteswipe.headlineQueue");
  localStorage.removeItem("biteswipe.headlineQueue.v2");
  setRandomBiteSwipeHeadline();
});
