let currentIndex = 0;
const cards = document.getElementById('cards');
const totalCards = document.querySelectorAll('.card').length;

function swipeLeft() {
  currentIndex = (currentIndex - 1 + totalCards) % totalCards;
  updateCardPosition();
}

function swipeRight() {
  currentIndex = (currentIndex + 1) % totalCards;
  updateCardPosition();
}

function updateCardPosition() {
  cards.style.transform = `translateX(-${currentIndex * 100}%)`;
}