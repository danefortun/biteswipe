function getFilters() {
  return {
    celiac: document.getElementById("celiac").checked,
    peanuts: document.getElementById("peanuts").checked,
    milk: document.getElementById("milk").checked,
    soy: document.getElementById("soy").checked,
    shellFish: document.getElementById("shellFish").checked,
    sesame: document.getElementById("sesame").checked,
    treenuts: document.getElementById("treenuts").checked,
    eggs: document.getElementById("Eggs").checked,

    cheapPrice: document.getElementById("cheapPrice").checked,
    mediumPrice: document.getElementById("mediumPrice").checked,
    expensivePrice: document.getElementById("expensivePrice").checked,

    distance: document.getElementById("myRange").value
  };
}

function updateFilters() {
  const filters = getFilters();
  console.log(filters);
  saveFilters(filters);
}

function saveFilters(filters) {
  fetch("/save_filters", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(filters)
  })
  .then(res => res.json())
  .then(data => console.log("Saved:", data))
  .catch(err => console.error("Error:", err));
  const filters = getFilters();
  console.log(filters);
  saveFilters(filters);
}

function saveFilters(filters) {
  fetch("/save_filters", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(filters)
  })
  .then(res => res.json())
  .then(data => console.log("Saved:", data))
  .catch(err => console.error("Error:", err));
}

document.addEventListener("DOMContentLoaded", function () {

  const inputs = document.querySelectorAll('.dropup-content input');

  inputs.forEach(input => {
    input.addEventListener("change", updateFilters);
  });

  const inputs = document.querySelectorAll('.dropup-content input');

  inputs.forEach(input => {
    input.addEventListener("change", updateFilters);
  });

  const slider = document.getElementById("myRange");
  const distanceValue = document.getElementById("distanceValue");
  const slider = document.getElementById("myRange");
  const distanceValue = document.getElementById("distanceValue");

  if (slider && distanceValue) {
  if (slider && distanceValue) {
    distanceValue.textContent = slider.value;

    slider.addEventListener("input", function () {
      distanceValue.textContent = this.value;
      updateFilters();
    });
  }

  fetch("/get_filters")
    .then(res => res.json())
    .then(saved => {
      if (!saved) return;

      for (let key in saved) {
        const element = document.getElementById(key);
        if (element) {
          if (element.type === "checkbox") {
            element.checked = saved[key];
          }
          if (element.type === "range") {
            element.value = saved[key];
            distanceValue.textContent = saved[key];
          }
        }
      }
      distanceValue.textContent = this.value;
      updateFilters();
    });
  }

  // ✅ MOVE THIS INSIDE HERE
  fetch("/get_filters")
    .then(res => res.json())
    .then(saved => {
      if (!saved) return;

      for (let key in saved) {
        const element = document.getElementById(key);
        if (element) {
          if (element.type === "checkbox") {
            element.checked = saved[key];
          }
          if (element.type === "range") {
            element.value = saved[key];
            distanceValue.textContent = saved[key];
          }
        }
      }
    });

});