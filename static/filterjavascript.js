let celiac = false;
let peanuts = false;
let milk = false;
let soy = false;
let fish = false;
let sesame = false;
let treeNuts = false;      // FIXED
let shellFish = false;     // FIXED
let eggs = false;

function updateFilters() {
  const checkboxes = document.querySelectorAll(
    '.dropup-content input[type="checkbox"]'
  );

  celiac   = checkboxes[0].checked;
  peanuts  = checkboxes[1].checked;
  milk     = checkboxes[2].checked;
  soy      = checkboxes[3].checked;
  fish     = checkboxes[4].checked;
  sesame   = checkboxes[5].checked;
  treeNuts = checkboxes[6].checked;   // FIXED
  shellFish= checkboxes[7].checked;   // FIXED
  eggs     = checkboxes[8].checked;

  console.log("Celiac:", celiac);
  console.log("Peanuts:", peanuts);
  console.log("Milk:", milk);
  console.log("Soy:", soy);
  console.log("Fish:", fish);
  console.log("Sesame:", sesame);
  console.log("Tree nuts:", treeNuts);
  console.log("Shell-Fish:", shellFish);
  console.log("Eggs:", eggs);
}

document.addEventListener("DOMContentLoaded", function () {

    const slider = document.getElementById("myRange");
    const distanceValue = document.getElementById("distanceValue");

    if (!slider || !distanceValue) {
        console.log("Slider or span not found.");
        return;
    }

    distanceValue.textContent = slider.value;

    slider.addEventListener("input", function () {
        distanceValue.textContent = this.value;
    });

});
