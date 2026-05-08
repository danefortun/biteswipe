function syncDeckState(options = {}) {
  if (typeof updateCardPosition === "function") {
    updateCardPosition();
  }

  if (options.persist !== false && typeof persistCurrentCardStack === "function") {
    persistCurrentCardStack();
  }

  if (typeof updateCardProgressSafely === "function") {
    updateCardProgressSafely();
  }

  if (typeof updateCardControls === "function") {
    updateCardControls();
  }
}
