let pendingInstallPrompt = null;

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  pendingInstallPrompt = event;
  document.querySelectorAll("[data-install-app]").forEach((button) => {
    button.hidden = false;
  });
});

window.addEventListener("appinstalled", () => {
  pendingInstallPrompt = null;
  document.querySelectorAll("[data-install-app]").forEach((button) => {
    button.hidden = true;
  });
});

document.addEventListener("DOMContentLoaded", () => {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/service-worker.js");
  }

  document.querySelectorAll("[data-install-app]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!pendingInstallPrompt) {
        return;
      }
      pendingInstallPrompt.prompt();
      await pendingInstallPrompt.userChoice;
      pendingInstallPrompt = null;
      button.hidden = true;
    });
  });
});
