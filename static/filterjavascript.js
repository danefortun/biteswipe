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
];

function myFunction() {
  toggleFooterPanel("filters");
}

function toggleFooterPanel(panelName) {
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
}

function getFilters() {
  const filters = {};

  checkboxFilterIds.forEach((id) => {
    const element = document.getElementById(id);
    filters[id] = element ? element.checked : false;
  });

  const distance = document.getElementById("myRange");

  filters.distance = distance ? Number(distance.value) : 50;
  filters.foodPreferences = getCheckedValues("foodPreferences");
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

  inputs.forEach((input) => {
    input.addEventListener("change", updateFilters);
  });

  const slider = document.getElementById("myRange");
  const distanceValue = document.getElementById("distanceValue");

  if (slider && distanceValue) {
    distanceValue.textContent = slider.value;

    slider.addEventListener("input", function () {
      distanceValue.textContent = this.value;
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
      restoreCheckedValues("hobbyInterests", saved.hobbyInterests);

      if (slider && distanceValue && saved.distance) {
        slider.value = saved.distance;
        distanceValue.textContent = saved.distance;
      }
    })
    .catch((err) => console.error("Error:", err));

  document.addEventListener("click", function (event) {
    const openDropup = document.querySelector(".dropup.is-open");

    if (!openDropup || openDropup.contains(event.target)) {
      return;
    }

    openDropup.classList.remove("is-open");

    document.querySelectorAll(".filter-trigger, .interests-trigger").forEach((trigger) => {
      trigger.setAttribute("aria-expanded", "false");
    });
  });
});
