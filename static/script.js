let currentIndex = 0;
let saved = ''
let restuarants = []
const cards = document.getElementById('cards');
const totalCards = document.querySelectorAll('.card').length;

function swipeLeft() {
  currentIndex = (currentIndex + 1) ;
  updateCardPosition();
  console.log("discarded")
}

function swipeRight() {
  saved += restuarants[currentIndex].name['text']
  saved +=','
  console.log("saved!" + restuarants[currentIndex])
  console.log(saved)
  currentIndex = (currentIndex + 1) ;
  updateCardPosition();
  saveFavorites()
  
}

function updateCardPosition() {
  cards.style.transform = `translateX(-${currentIndex * 100}%)`;
}

//the function below adds the restuarant to the page
function get_restaurant(){
        fetch('/get_restaurant')
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById("cards");
            container.innerHTML = "";

            data.places.forEach(result => {
                

const card = document.createElement("div");  
card.classList.add("card");

// Image
const img = document.createElement("img");
restuarants.push(result)
img.src = result.photo;
img.style.width = "100%";
img.style.height = "auto";   // keeps aspect ratio
card.appendChild(img);

// Name
const txt = document.createElement("p");
txt.textContent = result.name['text'];  // bracket notation for dictionary
txt.style.textAlign = "center";         // optional styling
card.appendChild(txt);

// Append card to container
container.appendChild(card);
            });
        });
console.log("cards refreshed")
    }


// the below function sends the users curtain coordinates to the database
function getAndSend() {

    // 1. Ask the browser for coordinates
    navigator.geolocation.getCurrentPosition((position) => {
        // 2. Put coordinates into the hidden inputs
        document.getElementById('lat_input').value = position.coords.latitude;
        document.getElementById('lng_input').value = position.coords.longitude;
        
        // 3. Immediately submit the form to your Flask route
        document.getElementById('locationForm').submit();
    }, (error) => {
        alert("Please enable location services in your browser.");
    });
    console.log("found location")
}

function saveFavorites(){
    fetch("/get_favorites",{method: "POST",headers: {"content-Type":"application/json"},body:JSON.stringify(saved)})
}