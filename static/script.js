let currentIndex = 0;
const cards = document.getElementById("cards");
let pointerStartX = 0;
let pointerCurrentX = 0;
let pointerStartY = 0;
let isDraggingCard = false;
let touchStartX = 0;
let touchStartY = 0;

function swipeLeft() {
  const currentRestaurant = getCurrentRestaurant();

  if (!currentRestaurant) {
    return;
  }

  recordRestaurantDecision("pass", currentRestaurant, currentIndex);
  moveToNextCard(`Passed ${currentRestaurant.name || "that spot"}.`);
}

async function swipeRight() {
  const currentRestaurant = getCurrentRestaurant();

  if (!currentRestaurant) {
    return;
  }

  const saved = await saveCurrentRestaurant();
  if (!saved) {
    return;
  }

  recordRestaurantDecision("save", currentRestaurant, currentIndex);
  moveToNextCard(`Saved ${currentRestaurant.name || "that spot"} to My Stuff.`);
}

async function saveCurrentRestaurant() {
  const currentRestaurant = getCurrentRestaurant();

  if (!currentRestaurant) {
    return false;
  }

  try {
    setDeckBusy(true);
    const response = await fetch("/save_restaurant", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(currentRestaurant),
    });
    const data = await response.json();

    if (typeof setRestaurantStatus === "function") {
      setRestaurantStatus(data.message || "Saved to My Stuff.");
    }

    if (!response.ok || data.ok === false) {
      console.error(data.message || "Unable to save restaurant.");
      return false;
    }

    return true;
  } catch (error) {
    if (typeof setRestaurantStatus === "function") {
      setRestaurantStatus("Unable to save that restaurant right now.");
    }
    return false;
  } finally {
    setDeckBusy(false);
  }
}

function getCurrentRestaurant() {
  const restaurants = window.currentRestaurantCards || [];
  return restaurants[currentIndex] || null;
}

function recordRestaurantDecision(action, restaurant, index) {
  if (!window.restaurantDecisionHistory) {
    window.restaurantDecisionHistory = [];
  }

  window.restaurantDecisionHistory.push({
    action,
    restaurant,
    index,
  });

  if (typeof incrementSessionStat === "function") {
    incrementSessionStat(action);
  }

  if (action === "pass" && typeof addPassedRestaurantToHistory === "function") {
    addPassedRestaurantToHistory(restaurant);
  }

  if (typeof rememberAvoidedRestaurant === "function") {
    rememberAvoidedRestaurant(restaurant);
  }

  if (typeof updateTasteProfile === "function") {
    updateTasteProfile(action, restaurant);
  }

  if (typeof rememberRestaurantDecision === "function") {
    rememberRestaurantDecision(action, restaurant);
  }

  if (typeof recordGroupSwipe === "function") {
    recordGroupSwipe(action, restaurant);
  }

  syncDeckState({ persist: false });
}

function undoLastDecision() {
  const history = window.restaurantDecisionHistory || [];
  const decision = history.pop();

  if (!decision) {
    return;
  }

  currentIndex = Math.max(Number(decision.index) || 0, 0);
  syncDeckState();

  if (typeof decrementSessionStat === "function") {
    decrementSessionStat(decision.action);
  }

  if (typeof setRestaurantStatus === "function") {
    const label = decision.action === "save" ? "save" : "pass";
    setRestaurantStatus(`Undid your ${label} on ${decision.restaurant?.name || "that spot"}.`);
  }
}

function moveToNextCard(statusMessage = "") {
  const totalCards = document.querySelectorAll(".card").length;

  if (totalCards === 0) {
    currentIndex = 0;
    syncDeckState();
    return;
  }

  currentIndex = Math.min(currentIndex + 1, totalCards);
  syncDeckState();

  if (typeof setRestaurantStatus === "function") {
    const atEnd = currentIndex >= totalCards;
    setRestaurantStatus(atEnd ? "Deck complete. Refresh for more restaurants or open My Stuff." : statusMessage);
  }
}

function updateCardPosition() {
  if (!cards) {
    return;
  }

  const allCards = Array.from(cards.querySelectorAll(".card"));
  const totalCards = allCards.length;
  const boundedIndex = Math.min(Math.max(currentIndex, 0), totalCards);

  cards.style.transform = `translateX(-${boundedIndex * 100}%)`;
  cards.dataset.currentIndex = String(boundedIndex);

  allCards.forEach((card, index) => {
    const offset = index - boundedIndex;
    card.classList.toggle("is-active", index === boundedIndex);
    card.classList.toggle("is-next", index === boundedIndex + 1);
    card.classList.toggle("is-past", index < boundedIndex);
    card.style.setProperty("--card-offset", String(offset));

    const isActive = index === boundedIndex;
    card.setAttribute("aria-hidden", String(!isActive));
    card.tabIndex = isActive ? 0 : -1;

    if ("inert" in card) {
      card.inert = !isActive;
    }

    if (!isActive) {
      card.classList.remove("is-flipped");
    }
  });
}

function updateCardControls() {
  const hasCurrent = Boolean(getCurrentRestaurant());
  const history = window.restaurantDecisionHistory || [];
  const passButton = document.getElementById("passCardButton");
  const saveButton = document.getElementById("saveCardButton");
  const undoButton = document.getElementById("undoCardButton");
  const shareButton = document.getElementById("shareCardButton");

  [passButton, saveButton, shareButton].forEach((button) => {
    if (button) {
      button.disabled = !hasCurrent;
    }
  });

  if (undoButton) {
    undoButton.disabled = history.length === 0;
  }

  if (typeof updateCurrentCardMeta === "function") {
    updateCurrentCardMeta();
  }
}

function updateCardProgressSafely() {
  if (typeof updateCardProgress === "function") {
    updateCardProgress();
  }
}

function persistCurrentCardStack() {
  if (typeof persistRestaurantCardStack === "function") {
    persistRestaurantCardStack();
  }
}

function setDeckBusy(isBusy) {
  document.querySelector(".card-stage")?.classList.toggle("is-saving", Boolean(isBusy));
}

function handleCardPointerDown(event) {
  if (!cards || event.target.closest("a, button, input, label, textarea, select")) {
    return;
  }

  if (!getCurrentRestaurant()) {
    return;
  }

  pointerStartX = event.clientX;
  pointerCurrentX = event.clientX;
  pointerStartY = event.clientY;
  isDraggingCard = true;
  cards.classList.add("is-dragging");
  cards.setPointerCapture?.(event.pointerId);
}

function handleCardPointerMove(event) {
  if (!isDraggingCard || !cards) {
    return;
  }

  pointerCurrentX = event.clientX;
  const deltaX = pointerCurrentX - pointerStartX;
  const deltaY = event.clientY - pointerStartY;

  if (Math.abs(deltaX) < 6 && Math.abs(deltaY) < 10) {
    return;
  }

  if (Math.abs(deltaX) > Math.abs(deltaY)) {
    event.preventDefault();
    cards.style.setProperty("--drag-x", `${deltaX}px`);
    cards.style.setProperty("--drag-rotate", `${Math.max(Math.min(deltaX / 18, 10), -10)}deg`);
    updateSwipeFeedback(deltaX);
  }
}

function handleCardPointerEnd(event) {
  if (!isDraggingCard || !cards) {
    return;
  }

  const deltaX = pointerCurrentX - pointerStartX;
  const wasSwipe = Math.abs(deltaX) > 80;
  isDraggingCard = false;
  cards.classList.remove("is-dragging");
  cards.style.removeProperty("--drag-x");
  cards.style.removeProperty("--drag-rotate");
  clearSwipeFeedback();
  cards.releasePointerCapture?.(event.pointerId);

  if (!wasSwipe) {
    return;
  }

  window.lastCardSwipeAt = Date.now();
  window.cardDragLock = true;
  window.setTimeout(() => {
    window.cardDragLock = false;
  }, 0);

  if (deltaX > 0) {
    swipeRight();
  } else {
    swipeLeft();
  }
}

function handleCardTouchStart(event) {
  if (!cards || event.target.closest("a, button, input, label, textarea, select")) {
    return;
  }

  const touch = event.changedTouches[0];
  if (!touch || !getCurrentRestaurant()) {
    return;
  }

  touchStartX = touch.clientX;
  touchStartY = touch.clientY;
}

function handleCardTouchMove(event) {
  if (!cards || !touchStartX) {
    return;
  }

  const touch = event.changedTouches[0];
  if (!touch) {
    return;
  }

  const deltaX = touch.clientX - touchStartX;
  const deltaY = touch.clientY - touchStartY;

  if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 12) {
    event.preventDefault();
    cards.classList.add("is-dragging");
    cards.style.setProperty("--drag-x", `${deltaX}px`);
    cards.style.setProperty("--drag-rotate", `${Math.max(Math.min(deltaX / 18, 10), -10)}deg`);
    updateSwipeFeedback(deltaX);
  }
}

function handleCardTouchEnd(event) {
  if (!cards || !touchStartX) {
    return;
  }

  const touch = event.changedTouches[0];
  const deltaX = touch ? touch.clientX - touchStartX : 0;
  const deltaY = touch ? touch.clientY - touchStartY : 0;
  const wasSwipe = Math.abs(deltaX) > 70 && Math.abs(deltaX) > Math.abs(deltaY) * 1.25;

  touchStartX = 0;
  touchStartY = 0;
  cards.classList.remove("is-dragging");
  cards.style.removeProperty("--drag-x");
  cards.style.removeProperty("--drag-rotate");
  clearSwipeFeedback();

  if (!wasSwipe) {
    return;
  }

  if (Date.now() - Number(window.lastCardSwipeAt || 0) < 500) {
    return;
  }

  window.lastCardSwipeAt = Date.now();
  window.cardDragLock = true;
  window.setTimeout(() => {
    window.cardDragLock = false;
  }, 0);

  if (deltaX > 0) {
    swipeRight();
  } else {
    swipeLeft();
  }
}

function updateSwipeFeedback(deltaX) {
  const card = document.querySelector(".card.is-active");
  if (!card) return;

  const strength = Math.min(Math.abs(deltaX) / 130, 1).toFixed(2);
  card.style.setProperty("--swipe-feedback-opacity", strength);
  card.dataset.swipeIntent = deltaX > 0 ? "save" : "pass";
}

function clearSwipeFeedback() {
  document.querySelectorAll(".card[data-swipe-intent]").forEach((card) => {
    card.style.removeProperty("--swipe-feedback-opacity");
    delete card.dataset.swipeIntent;
  });
}

function handleDeckKeyboard(event) {
  const activeElement = document.activeElement;
  const isTyping = activeElement && ["INPUT", "TEXTAREA", "SELECT"].includes(activeElement.tagName);

  if (isTyping) {
    return;
  }

  if (event.key === "ArrowLeft") {
    event.preventDefault();
    swipeLeft();
  }

  if (event.key === "ArrowRight") {
    event.preventDefault();
    swipeRight();
  }

  if (event.key.toLowerCase() === "u") {
    event.preventDefault();
    undoLastDecision();
  }
}

if (cards) {
  cards.addEventListener("pointerdown", handleCardPointerDown);
  cards.addEventListener("pointermove", handleCardPointerMove);
  cards.addEventListener("pointerup", handleCardPointerEnd);
  cards.addEventListener("pointercancel", handleCardPointerEnd);
  cards.addEventListener("touchstart", handleCardTouchStart, { passive: true });
  cards.addEventListener("touchmove", handleCardTouchMove, { passive: false });
  cards.addEventListener("touchend", handleCardTouchEnd, { passive: true });
}

document.addEventListener("keydown", handleDeckKeyboard);
