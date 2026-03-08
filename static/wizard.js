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

async function startSession() {
  const res = await fetch("/wizard/session/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  });
  const data = await res.json();
  sessionId = data.session_id;
}

function showStep(index) {
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
    privacy_level: fd.get("privacy_level"),
    safety_need: fd.get("safety_need"),
    width_cm: Number(fd.get("width_cm")),
    height_cm: fd.get("height_cm") ? Number(fd.get("height_cm")) : null,
    allow_diy: fd.get("allow_diy") === "on",
    interior_reflection_sensitive: fd.get("interior_reflection_sensitive") === "on",
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

  overlay.classList.remove("hidden");

  if (!validateCurrentStep()) {
    overlay.classList.add("hidden");
    return;
  }

  await new Promise(r => setTimeout(r, 50));

  await savePartial();

  overlay.classList.add("hidden");

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
    humanSummary.textContent = data.summary;
    renderResults(data.results);
    resultSection.classList.remove("hidden");
    resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    alert(err.message || "Valami hiba történt.");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Ajánlások mutatása";
    overlay.classList.add("hidden");
  }
});

function renderResults(results) {
  if (!results || results.length === 0) {
    resultCards.innerHTML = `
      <div class="lead-box">
        <h3>Most nem találtunk pontos egyezést</h3>
        <p>
          Ettől még lehet jó megoldás, csak érdemes egyedi átnézés alapján választani.
          Add meg az email címedet lent, és segítünk.
        </p>
      </div>
    `;
    return;
  }

  resultCards.innerHTML = results.map(item => `
    <article class="result-card">
      <div>
        ${item.image
          ? `<img src="${item.image}" alt="${escapeHtml(item.name)}">`
          : `<div style="height:100%;min-height:180px;background:#f3f5f9;"></div>`
        }
      </div>
      <div class="result-body">
        <h3>${escapeHtml(item.name)}</h3>
        <div class="result-meta">
          <span class="pill">Cikkszám: ${escapeHtml(item.sku)}</span>
          <span class="pill">Család: ${escapeHtml(item.family)}</span>
          <span class="pill">Pontszám: ${Number(item.score).toFixed(1)}</span>
        </div>
        <a class="result-link" href="${item.url}" target="_blank" rel="noopener noreferrer">
          Megnézem a terméket
        </a>
      </div>
    </article>
  `).join("");
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

(async function init() {
  await startSession();
  showStep(0);
})();