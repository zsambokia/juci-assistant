const form = document.getElementById("wizardForm");
const steps = [...document.querySelectorAll(".step")];
const nextBtn = document.getElementById("nextBtn");
const prevBtn = document.getElementById("prevBtn");
const submitBtn = document.getElementById("submitBtn");
const overlay = document.getElementById("loadingOverlay");

const progressFill = document.getElementById("progressFill");
const progressText = document.getElementById("progressText");

const resultSection = document.getElementById("resultSection");
const resultCards = document.getElementById("resultCards");
const humanSummary = document.getElementById("humanSummary");

const leadForm = document.getElementById("leadForm");
const leadEmail = document.getElementById("leadEmail");
const leadName = document.getElementById("leadName");
const leadMessage = document.getElementById("leadMessage");

let currentStep = 0;
let sessionId = null;
let lastAnswers = null;

function hideGlassSteps(){

  if(!isPolycarbonateFlow()) return;

  steps.forEach((step,i)=>{
    if(i > 0 && i < 9){

      step.style.display = "none";

      step.querySelectorAll("[required]").forEach(el=>{
        el.required = false;
      });

    }
  });

}

function showStep(index) {
  
  const goal = document.querySelector('input[name="main_goal"]:checked')?.value;

  if (goal !== "heat_privacy") {
    if (index === 5) index = 6;
    if (index === 6 && currentStep === 7) index = 4;
  }

  steps.forEach((step, i) => {
    step.classList.toggle("active", i === index);
  });

  currentStep = index;

  let total;
  let current;

  if(isPolycarbonateFlow()){

    total = 2;

    if(currentStep === 0){
      current = 1;
    }else{
      current = 2;
    }

  }else{

    total = steps.length;
    current = currentStep + 1;

  }

  progressFill.style.width = `${(current / total) * 100}%`;
  progressText.textContent = `${current} / ${total}`;

  prevBtn.classList.toggle("hidden", currentStep === 0);
  
  const isSizeStep = currentStep === 9;

    if(isPolycarbonateFlow()){

        nextBtn.classList.toggle("hidden", isSizeStep);
        submitBtn.classList.toggle("hidden", !isSizeStep);

        }else{

        nextBtn.classList.toggle("hidden", currentStep === steps.length - 1);
        submitBtn.classList.toggle("hidden", currentStep !== steps.length - 1);

    }

}


function buildPayload() {
  const formData = new FormData(form);

  const surface = formData.get("surface");

  if (surface === "polycarbonate") {
    return {
      session_id: sessionId,
      surface: "polycarbonate",
      width_cm: Number(formData.get("width_cm")),
      height_cm: formData.get("height_cm") ? Number(formData.get("height_cm")) : null,
      window_type: "other",
      glass_type: "unknown",
      install_side: "unknown",
      main_goal: "heat",
      reflectivity_tolerance: "not_mirror",
      brightness_preference: "medium",
      privacy_level: "none",
      allow_diy: true,
      interior_reflection_sensitive: false
    };
  }

  return {
    session_id: sessionId,
    surface: formData.get("surface"),
    window_type: formData.get("window_type"),
    glass_type: formData.get("glass_type"),
    install_side: formData.get("install_side"),
    main_goal: formData.get("main_goal"),
    privacy_level: formData.get("privacy_level"),
    reflectivity_tolerance: formData.get("reflectivity_tolerance"),
    brightness_preference: formData.get("brightness_preference"),
    interior_reflection_sensitive: formData.get("interior_reflection_sensitive") === "true",
    width_cm: Number(formData.get("width_cm")),
    height_cm: formData.get("height_cm") ? Number(formData.get("height_cm")) : null,
    allow_diy: true
  };
}

function validateCurrentStep() {
  const activeStep = steps[currentStep];
  const requiredInputs = [...activeStep.querySelectorAll("[required]")];

  for (const input of requiredInputs) {
    if (input.type === "radio") {
      const group = form.querySelectorAll(`input[name="${input.name}"]`);
      const checked = [...group].some(item => item.checked);
      if (!checked) {
        alert("Kérlek, válassz egy lehetőséget, hogy tovább tudjunk lépni.");
        return false;
      }
    } else if (!input.value) {
      input.focus();
      alert("Kérlek, töltsd ki ezt a mezőt is.");
      return false;
    }
  }

  return true;
}


nextBtn.addEventListener("click", async () => {
    if (currentStep === 0 && isPolycarbonateFlow()) {

    hideGlassSteps();

    showStep(9);

    window.scrollTo({ top: 0, behavior: "smooth" });

    return;
    }

    if (!validateCurrentStep()) {
        return;
    }

  showStep(currentStep + 1);
  window.scrollTo({ top: 0, behavior: "smooth" });

});

prevBtn.addEventListener("click", () => {

  resultSection.classList.add("hidden");

  if(isPolycarbonateFlow() && currentStep === 9){
      showStep(0);
  } else {
      showStep(currentStep - 1);
  }

  window.scrollTo({ top: 0, behavior: "smooth" });

});

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  if (!validateCurrentStep()) return;

  const payload = buildPayload();
  lastAnswers = payload;

  submitBtn.disabled = true;
  submitBtn.textContent = "Ajánlások betöltése...";
  overlay.classList.remove("hidden");

  try {
    const res = await fetch("/wizard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Hiba történt.");
    }

    sessionId = data.session_id;

    window.location.href = "/hovedo/eredmeny?session=" + data.session_id;
    return;

  } catch (err) {
    alert(err.message || "Valami hiba történt.");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Ajánlások mutatása";
    overlay.classList.add("hidden");
  }
});

const perfect = results.filter(r => r.exact_match);
const recommended = results.filter(r => !r.exact_match);

let html = "";


/* =========================
   ⭐ PERFECT MATCH
========================= */

if(perfect.length){

html += `
<section class="result-section perfect">

<h2 class="section-title">
⭐ Kiemelt ajánlataink
</h2>

<p class="section-sub">
Ezek a fóliák a megadott igényeidhez a legjobban illeszkednek.
</p>

<div class="result-grid">
`;

html += perfect.map(renderCard).join("");

html += `
</div>
</section>
`;

}


/* =========================
   ⚪ RECOMMENDED
========================= */

if(recommended.length){

html += `
<section class="result-section recommended">

<h2 class="section-title secondary">
⚪ Nem minden igényedhez igazodik, de érdekelhet
</h2>

<p class="section-sub">
Ezek a fóliák közel állnak az igényeidhez,
de egy-két feltételben eltérnek.
</p>

<div class="result-grid">
`;

html += recommended.map(renderCard).join("");

html += `
</div>
</section>
`;


container.innerHTML = html;

}

function renderCard(item){

    return `
    <article class="result-card ${item.exact_match ? "perfect-card" : ""}">
    ${item.is_recommended
        ? `<div class="juci-pick">⭐ Fóliás Juci ajánlása</div>`
    : ``}

    <div class="card-image">

    ${item.image
    ? `<img src="${item.image}" alt="${item.name}">`
    : `<div class="img-placeholder"></div>`
    }

    </div>

    <div class="result-body">

    <h3>${item.name}</h3>

    <div class="result-meta">

    <span class="pill">Cikkszám: ${item.sku}</span>
    <span class="pill">${item.family}</span>

    <span class="match-badge">
    ${matchLabel(item)}
    </span>

    </div>

    <div class="spec-grid">

    <div class="spec">
    <div class="label">Hővédelem</div>
    <div class="stars">${stars(item.heat_stars)}</div>
    <div class="value">${item.tser}%</div>
    </div>

    <div class="spec">
    <div class="label">Fényáteresztés</div>
    <div class="stars">${stars(item.light_stars)}</div>
    <div class="value">${item.vlt}%</div>
    </div>

    <div class="spec">
    <div class="label">Belátásvédelem</div>
    <div class="stars">${stars(item.privacy_stars)}</div>
    <div class="value">${item.reflect_ext}%</div>
    </div>

    </div>

    <a class="result-link"
    href="${item.url}"
    target="_blank">

    Megnézem a terméket

    </a>

    </div>

    </article>
    `;

}

if (leadForm) {
    leadForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (submitBtn.disabled) return;

    if (!validateCurrentStep()) return;

    if (!sessionId) {
        leadMessage.textContent = "Előbb kérlek futtasd le az ajánlót.";
        return;
    }

    try {
        const res = await fetch("/wizard/lead", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            session_id: sessionId,
            email: leadEmail.value,
            name: leadName.value || null
        })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Nem sikerült elküldeni.");

        leadMessage.textContent = "Köszönjük! Rögzítettük az email címedet.";
        leadForm.reset();
    } catch (err) {
        leadMessage.textContent = err.message || "Hiba történt az elküldésnél.";
    }
    }); 
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function matchLabel(item){

    if(item.exact_match){
    return "🏆 Tökéletes választás";
    }

    if(item.score > 50){
    return "👍 Majdnem tökéletes";
    }

    if(item.score > 40){
    return "🙂 Jó alternatíva";
    }

    return "ℹ Megfontolható";

}


function getSelectedSurface() {
  return document.querySelector('input[name="surface"]:checked')?.value;
}

function isPolycarbonateFlow() {
  return getSelectedSurface() === "polycarbonate";
}

function stars(n){
    return "★".repeat(n) + "☆".repeat(5-n);
}

document.querySelectorAll('input[name="surface"]').forEach(el=>{
  el.addEventListener("change", hideGlassSteps);
});


(async function init() {
  showStep(0);
})();


