let currentIndex = 0;
const cards = document.getElementById('cards');
const totalCards = document.querySelectorAll('.card').length;

function swipeLeft() {
  currentIndex = (currentIndex + 1) ;
  updateCardPosition();
}

function swipeRight() {
  currentIndex = (currentIndex + 1) ;
  updateCardPosition();
}

function updateCardPosition() {
  cards.style.transform = `translateX(-${currentIndex * 100}%)`;
}