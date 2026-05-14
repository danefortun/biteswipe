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

  document.querySelectorAll(`input[name="${name}"]`).forEach((input) => {
    input.checked = selected.has(String(input.value).toLowerCase());
  });
}

document.addEventListener("DOMContentLoaded", function () {
  const inputs = document.querySelectorAll(".dropup-content input");
  const closeButtons = document.querySelectorAll("[data-close-footer-panel]");

  inputs.forEach((input) => {
    input.addEventListener("change", updateFilters);
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
