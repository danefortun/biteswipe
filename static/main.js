(function () {
  "use strict";

  const form = document.querySelector(".validate-form");
  if (!form) {
    return;
  }

  const inputs = Array.from(form.querySelectorAll(".validate-input .input100"));

  form.addEventListener("submit", function (event) {
    let isValid = true;

    inputs.forEach((input) => {
      if (!validate(input)) {
        showValidate(input);
        isValid = false;
      }
    });

    if (!isValid) {
      event.preventDefault();
    }
  });

  inputs.forEach((input) => {
    input.addEventListener("focus", function () {
      hideValidate(input);
    });
  });

  function validate(input) {
    const value = input.value.trim();

    if (input.type === "email" || input.name === "email") {
      return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
    }

    return value !== "";
  }

  function showValidate(input) {
    input.parentElement.classList.add("alert-validate");
  }

  function hideValidate(input) {
    input.parentElement.classList.remove("alert-validate");
  }
})();
