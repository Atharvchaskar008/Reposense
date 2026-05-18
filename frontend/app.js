const analyzeBtn = document.getElementById("analyzeBtn");

const logsContainer = document.getElementById("logs");

const dependencyResults = document.getElementById("dependencyResults");
const securityResults = document.getElementById("securityResults");
const fixResults = document.getElementById("fixResults");

function addLog(message) {
  const log = document.createElement("div");
  log.classList.add("log");

  log.textContent = `> ${message}`;

  logsContainer.appendChild(log);

  logsContainer.scrollTop = logsContainer.scrollHeight;
}

analyzeBtn.addEventListener("click", async () => {

  const repoUrl = document.getElementById("repoInput").value;

  if (!repoUrl) {
    alert("Please enter a GitHub repository URL.");
    return;
  }

  // Clear old data
  logsContainer.innerHTML = "";

  dependencyResults.innerHTML = "Analyzing...";
  securityResults.innerHTML = "Analyzing...";
  fixResults.innerHTML = "Analyzing...";

  addLog("Starting repository analysis...");
  addLog("Connecting to Jac backend...");

  try {

    const response = await fetch("http://localhost:8000/analyze", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        repo_url: repoUrl
      })
    });

    const data = await response.json();

    addLog("Dependency agent completed.");
    addLog("Security agent completed.");
    addLog("Fix agent completed.");

    // Dependency Results
    dependencyResults.innerHTML = `
      <pre>${JSON.stringify(data.dependencies, null, 2)}</pre>
    `;

    // Security Results
    securityResults.innerHTML = `
      <pre>${JSON.stringify(data.security, null, 2)}</pre>
    `;

    // Fix Results
    fixResults.innerHTML = `
      <pre>${JSON.stringify(data.fixes, null, 2)}</pre>
    `;

    addLog("Analysis completed successfully.");

  } catch (error) {

    console.error(error);

    addLog("Error connecting to backend.");

    dependencyResults.innerHTML = "Error";
    securityResults.innerHTML = "Error";
    fixResults.innerHTML = "Error";
  }
});