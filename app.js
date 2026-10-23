const form = document.getElementById("trip-form");
let latestResult = null;
let costChart, distanceChart;

const money = n => "₹" + Number(n).toLocaleString("en-IN", {minimumFractionDigits: 2, maximumFractionDigits: 2});

async function loadAnalytics() {
  const costCanvas = document.getElementById("cost-chart");
  if (!costCanvas) return;
  try {
    const response = await fetch("/api/analytics");
    const data = await response.json();
    const labels = data.labels.length ? data.labels : ["No trips yet"];
    const costs = data.costs.length ? data.costs : [0];
    const distances = data.distances.length ? data.distances : [0];
    const common = {responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}};
    if (costChart) costChart.destroy();
    if (distanceChart) distanceChart.destroy();
    costChart = new Chart(costCanvas, {type:"bar", data:{labels, datasets:[{label:"Cost (₹)", data:costs, borderRadius:7}]}, options:{...common, scales:{y:{beginAtZero:true}}}});
    distanceChart = new Chart(document.getElementById("distance-chart"), {type:"line", data:{labels, datasets:[{label:"Distance (km)", data:distances, tension:.3, fill:true}]}, options:{...common, scales:{y:{beginAtZero:true}}}});
  } catch (e) { console.warn("Analytics could not load", e); }
}
loadAnalytics();

if (form) {
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const error = document.getElementById("error");
    error.textContent = "";
    const fd = new FormData(form);
    const payload = Object.fromEntries(fd.entries());
    payload.round_trip = form.querySelector('[name="round_trip"]').checked;
    try {
      const response = await fetch("/api/calculate", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not calculate this trip.");
      latestResult = data;
      document.getElementById("cost-result").textContent = money(data.estimated_cost);
      document.getElementById("fuel-result").textContent = data.fuel_needed.toFixed(2) + " L";
      document.getElementById("distance-result").textContent = data.distance_km.toFixed(1) + " km";
      document.getElementById("perkm-result").textContent = money(data.cost_per_km);
      const list = document.getElementById("tips");
      list.innerHTML = "";
      data.tips.forEach(tip => { const li = document.createElement("li"); li.textContent = tip; list.appendChild(li); });
      document.getElementById("result-panel").classList.add("has-result");
      await loadAnalytics();
      setTimeout(() => location.reload(), 1200);
    } catch (e) { error.textContent = e.message; }
  });
}

const speak = text => {
  if (!("speechSynthesis" in window)) { alert("Text-to-speech is not supported by this browser."); return; }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-IN";
  window.speechSynthesis.speak(utterance);
};
document.getElementById("speak-result")?.addEventListener("click", () => {
  if (!latestResult) { speak("Please calculate a trip first."); return; }
  speak(`Your trip from ${latestResult.start_location} to ${latestResult.destination} is estimated to cost ${latestResult.estimated_cost} rupees. You need ${latestResult.fuel_needed} litres of fuel for ${latestResult.distance_km} kilometres.`);
});

document.getElementById("voice-input")?.addEventListener("click", () => {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const status = document.getElementById("voice-status");
  if (!SpeechRecognition) { status.textContent = "Voice recognition is not available in this browser. Try a supported browser or type the details."; return; }
  const recognition = new SpeechRecognition();
  recognition.lang = "en-IN";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  status.textContent = "Listening… say distance, mileage, and fuel price, for example: distance 250 kilometres, mileage 18, fuel price 105.";
  recognition.onresult = event => {
    const transcript = event.results[0][0].transcript;
    status.textContent = "Heard: " + transcript;
    const nums = transcript.match(/\d+(?:\.\d+)?/g);
    if (nums && nums.length >= 3) {
      form.elements.distance_km.value = nums[0];
      form.elements.mileage_kmpl.value = nums[1];
      form.elements.fuel_price.value = nums[2];
      status.textContent += " — filled distance, mileage, and fuel price. Please verify, then calculate.";
    } else {
      status.textContent += " — please say three numbers in this order: distance, mileage, fuel price.";
    }
  };
  recognition.onerror = event => status.textContent = "Voice input error: " + event.error + ". You can type the values instead.";
  recognition.start();
});
