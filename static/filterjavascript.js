const checkboxFilterIds = [
  "celiac",
  "peanuts",
  "milk",
  "soy",
  "shellFish",
  "sesame",
  "treenuts",
  "eggs",
  "cheapPrice",
  "mediumPrice",
  "expensivePrice",
  "openNow",
  "outdoorSeating",
  "takeoutOnly",
  "dineIn",
];
const quickInterestMaxLength = 16;
const blockedQuickInterestTerms = new Set([
  "bastard",
  "bitch",
  "bullshit",
  "chink",
  "cunt",
  "dick",
  "dyke",
  "fag",
  "fuck",
  "gook",
  "kike",
  "nazi",
  "nigga",
  "nigger",
  "paki",
  "prick",
  "retard",
  "shit",
  "slut",
  "tranny",
  "whore",
]);

function myFunction(event) {
  toggleFooterPanel("filters", event);
}

function closeFooterPanels() {
  document.querySelectorAll(".dropup.is-open").forEach((dropup) => {
    dropup.classList.remove("is-open");
  });

  document.querySelectorAll(".filter-trigger, .interests-trigger").forEach((trigger) => {
    trigger.setAttribute("aria-expanded", "false");
  });

  document.body.classList.remove("footer-panel-open");
}

function toggleFooterPanel(panelName, event) {
  if (event && typeof event.stopPropagation === "function") {
    event.stopPropagation();
  }

  const target = panelName === "interests" ? "myInterestsDropup" : "myDropup";
  const triggerSelector = panelName === "interests" ? ".interests-trigger" : ".filter-trigger";
  const menu = document.getElementById(target);

  if (!menu) {
    return;
  }

  document.querySelectorAll(".dropup").forEach((dropup) => {
    if (!dropup.contains(menu)) {
      dropup.classList.remove("is-open");
    }
  });

  document.querySelectorAll(".filter-trigger, .interests-trigger").forEach((trigger) => {
    if (!trigger.matches(triggerSelector)) {
      trigger.setAttribute("aria-expanded", "false");
    }
  });

  const dropup = menu.closest(".dropup");
  const trigger = document.querySelector(triggerSelector);
  const isOpen = dropup ? dropup.classList.toggle("is-open") : false;

  if (trigger) {
    trigger.setAttribute("aria-expanded", String(isOpen));
  }

  document.body.classList.toggle("footer-panel-open", isOpen);
}

function getFilters() {
  const filters = {};

  checkboxFilterIds.forEach((id) => {
    const element = document.getElementById(id);
    filters[id] = element ? element.checked : false;
  });

  const distance = document.getElementById("myRange");
  const minRating = document.getElementById("minRatingRange");

  filters.distance = distance ? Number(distance.value) : 2;
  filters.minRating = minRating ? Number(minRating.value) : 0;
  filters.foodPreferences = getCheckedValues("foodPreferences");
  filters.cuisineExclusions = getCheckedValues("cuisineExclusions");
  filters.hobbyInterests = getCheckedValues("hobbyInterests");

  return filters;
}

function getCheckedValues(name) {
  return Array.from(document.querySelectorAll(`input[name="${name}"]:checked`)).map(
    (input) => input.value
  );
}

function normalizeQuickInterest(value) {
  return String(value || "").replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
}

function validateQuickInterest(value) {
  const text = normalizeQuickInterest(value);
  if (!text) return "Enter a quick interest first.";
  if (text.length > quickInterestMaxLength) return "Quick interests must be 16 characters or fewer.";
  if (!/^[A-Za-z0-9 ]+$/.test(text)) return "Use letters, numbers, and spaces only.";

  const compact = text.toLowerCase().replace(/[^a-z0-9]+/g, "");
  for (const term of blockedQuickInterestTerms) {
    if (compact.includes(term)) return "That quick interest is not allowed.";
  }

  return "";
}

function quickInterestId(value) {
  return `customQuickInterest-${normalizeQuickInterest(value).toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}

function isBuiltInFoodPreference(value) {
  const normalized = normalizeQuickInterest(value).toLowerCase();
  return Array.from(document.querySelectorAll('input[name="foodPreferences"]'))
    .some((input) => normalizeQuickInterest(input.value).toLowerCase() === normalized);
}

function addCustomQuickInterest(value, options = {}) {
  const text = normalizeQuickInterest(value);
  const error = validateQuickInterest(text);
  const errorLabel = document.getElementById("quickInterestError");
  const list = document.getElementById("customQuickInterestList");

  if (error) {
    if (errorLabel) errorLabel.textContent = error;
    return false;
  }

  if (errorLabel) errorLabel.textContent = "";

  const existing = Array.from(document.querySelectorAll('input[name="foodPreferences"]'))
    .find((input) => normalizeQuickInterest(input.value).toLowerCase() === text.toLowerCase());
  if (existing) {
    existing.checked = true;
    return true;
  }

  if (!list) return false;

  const id = quickInterestId(text);
  const label = document.createElement("label");
  label.className = "filter-option custom-quick-interest";
  label.setAttribute("for", id);

  const input = document.createElement("input");
  input.type = "checkbox";
  input.id = id;
  input.name = "foodPreferences";
  input.value = text;
  input.checked = options.checked !== false;
  input.addEventListener("change", updateFilters);

  label.append(input, ` ${text}`);
  list.appendChild(label);
  return true;
}

function updateFilters() {
  saveFilters(getFilters());
}

function saveFilters(filters) {
  fetch("/save_filters", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(filters),
  })
    .then((res) => res.json())
    .then(() => {
      clearCachedRestaurantStack();
      if (typeof setRestaurantStatus === "function") {
        setRestaurantStatus("Filters saved. Press Refresh cards to apply them.");
      }
    })
    .catch((err) => console.error("Error:", err));
}

function clearCachedRestaurantStack() {
  if (window.restaurantCardStorageKey) {
    localStorage.removeItem(window.restaurantCardStorageKey);
  }
}

function restoreCheckedValues(name, values) {
  const selected = new Set((values || []).map((value) => String(value).toLowerCase()));

  if (name === "foodPreferences") {
    (values || []).forEach((value) => {
      if (!isBuiltInFoodPreference(value)) {
        addCustomQuickInterest(value, { checked: true });
      }
    });
  }

  document.querySelectorAll(`input[name="${name}"]`).forEach((input) => {
    input.checked = selected.has(String(input.value).toLowerCase());
  });
}

document.addEventListener("DOMContentLoaded", function () {
  const inputs = document.querySelectorAll(".dropup-content input");
  const closeButtons = document.querySelectorAll("[data-close-footer-panel]");
  const quickInterestForm = document.getElementById("quickInterestForm");
  const customQuickInterest = document.getElementById("customQuickInterest");

  inputs.forEach((input) => {
    input.addEventListener("change", updateFilters);
  });

  quickInterestForm?.addEventListener("submit", function (event) {
    event.preventDefault();
    if (addCustomQuickInterest(customQuickInterest?.value || "")) {
      if (customQuickInterest) customQuickInterest.value = "";
      updateFilters();
    }
  });

  closeButtons.forEach((button) => {
    button.addEventListener("click", function (event) {
      event.preventDefault();
      closeFooterPanels();
    });
  });

  const slider = document.getElementById("myRange");
  const distanceValue = document.getElementById("distanceValue");
  const minRating = document.getElementById("minRatingRange");
  const minRatingValue = document.getElementById("minRatingValue");

  if (slider && distanceValue) {
    distanceValue.textContent = slider.value;

    slider.addEventListener("input", function () {
      distanceValue.textContent = this.value;
      updateFilters();
    });
  }

  if (minRating && minRatingValue) {
    minRatingValue.textContent = Number(minRating.value).toFixed(1);

    minRating.addEventListener("input", function () {
      minRatingValue.textContent = Number(this.value).toFixed(1);
      updateFilters();
    });
  }

  fetch("/get_filters")
    .then((res) => res.json())
    .then((saved) => {
      if (!saved) {
        return;
      }

      checkboxFilterIds.forEach((id) => {
        const element = document.getElementById(id);
        if (element) {
          element.checked = Boolean(saved[id]);
        }
      });

      restoreCheckedValues("foodPreferences", saved.foodPreferences);
      restoreCheckedValues("cuisineExclusions", saved.cuisineExclusions);
      restoreCheckedValues("hobbyInterests", saved.hobbyInterests);

      if (slider && distanceValue && saved.distance) {
        slider.value = saved.distance;
        distanceValue.textContent = saved.distance;
      }

      if (minRating && minRatingValue && saved.minRating !== undefined) {
        minRating.value = saved.minRating;
        minRatingValue.textContent = Number(saved.minRating).toFixed(1);
      }
    })
    .catch((err) => console.error("Error:", err));

  document.addEventListener("click", function (event) {
    const openDropup = document.querySelector(".dropup.is-open");

    if (!openDropup || openDropup.contains(event.target)) {
      return;
    }

    closeFooterPanels();
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closeFooterPanels();
    }
  });
});
