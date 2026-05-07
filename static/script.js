let currentIndex = 0;
const cards = document.getElementById("cards");

function swipeLeft() {
  moveToNextCard();
}

async function swipeRight() {
  await saveCurrentRestaurant();
  moveToNextCard();
}

async function saveCurrentRestaurant() {
  const currentRestaurant = getCurrentRestaurant();

  if (!currentRestaurant) {
    return;
  }

  try {
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

    if (!response.ok) {
      console.error(data.message || "Unable to save restaurant.");
    }
  } catch (error) {
    if (typeof setRestaurantStatus === "function") {
      setRestaurantStatus("Unable to save that restaurant right now.");
    }
  }
}

function getCurrentRestaurant() {
  const restaurants = window.currentRestaurantCards || [];
  return restaurants[currentIndex] || null;
}

function moveToNextCard() {
  const totalCards = document.querySelectorAll(".card").length;
  if (totalCards === 0) {
    currentIndex = 0;
    updateCardPosition();
    persistCurrentCardStack();
    return;
  }

  currentIndex = Math.min(currentIndex + 1, totalCards - 1);
  updateCardPosition();
  persistCurrentCardStack();
}

function updateCardPosition() {
  if (!cards) {
    return;
  }

  cards.style.transform = `translateX(-${currentIndex * 100}%)`;
}

function persistCurrentCardStack() {
  if (typeof persistRestaurantCardStack === "function") {
    persistRestaurantCardStack();
  }
}
