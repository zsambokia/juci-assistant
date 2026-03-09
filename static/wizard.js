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



function showStep(index) {
  
  const goal = document.querySelector('input[name="main_goal"]:checked')?.value;


    // privacy step kihagyása előre és vissza is
    if (goal !== "heat_privacy") {
        if (index === 5) index = 6;
        if (index === 6 && currentStep === 7) index = 4;
    }


    steps.forEach((step, i) => {
    step.classList.toggle("active", i === index);
  });

  currentStep = index;
  const total = steps.length;
  const current = currentStep + 1;

  progressFill.style.width = `${(current / total) * 100}%`;
  progressText.textContent = `${current} / ${total}`;

  prevBtn.classList.toggle("hidden", currentStep === 0);
  nextBtn.classList.toggle("hidden", currentStep === total - 1);
  submitBtn.classList.toggle("hidden", currentStep !== total - 1);
}

function getFormDataObject() {
  const fd = new FormData(form);
  return {
    session_id: sessionId,
    surface: fd.get("surface"),
    window_type: fd.get("window_type"),
    glass_type: fd.get("glass_type"),
    install_side: fd.get("install_side"),
    main_goal: fd.get("main_goal"),
    reflectivity_tolerance: fd.get("reflectivity_tolerance"),
    brightness_preference: fd.get("brightness_preference"),
    privacy_level: fd.get("privacy_level") || "none",
    safety_need: fd.get("safety_need"),
    width_cm: Number(fd.get("width_cm")),
    height_cm: fd.get("height_cm") ? Number(fd.get("height_cm")) : null,
    allow_diy: fd.get("allow_diy") === "on",
    interior_reflection_sensitive: fd.get("interior_reflection_sensitive") === "true",
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

async function savePartial() {
  const answers = getFormDataObject();

  const payload = {
    session_id: sessionId,
    surface: answers.surface || null,
    window_type: answers.window_type || null,
    glass_type: answers.glass_type || null,
    install_side: answers.install_side || null,
    width_cm: answers.width_cm || null,
    height_cm: answers.height_cm || null,
    privacy_required: ["daytime", "day_night", "decor"].includes(answers.privacy_level),
    reflectivity_preference:
      answers.reflectivity_tolerance === "mirror_ok" ? "mirror" :
      answers.reflectivity_tolerance ? "neutral" : null,
    result_count: null
  };

  await fetch("/wizard/session/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}


nextBtn.addEventListener("click", async () => {

  if (!validateCurrentStep()) {
    return;
  }

  showStep(currentStep + 1);
  window.scrollTo({ top: 0, behavior: "smooth" });

});

prevBtn.addEventListener("click", () => {

  resultSection.classList.add("hidden");

  showStep(currentStep - 1);
  window.scrollTo({ top: 0, behavior: "smooth" });

});

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  if (!validateCurrentStep()) return;

  const payload = getFormDataObject();
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

function renderResults(data){

    const results = Array.isArray(data.results) ? data.results : [];
    const container = document.getElementById("resultCards");

    if(results.length === 0){

    container.innerHTML = `
    <div class="lead-box">

    <h3>Nincs pontos egyezés</h3>

    <p>
    ${data.failure_reason || 
    "Nem találtunk minden feltételnek megfelelő fóliát."}
    </p>

    </div>
    `;

    return;
}

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

}

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


function stars(n){
    return "★".repeat(n) + "☆".repeat(5-n);
}

(async function init() {
  showStep(0);
})();


