const API_BASE_URL = "http://127.0.0.1:8000";

async function postJson(endpoint, payload) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.detail || `Request failed: ${endpoint}`);
  }

  return data;
}

export async function validateForgeMission(mission) {
  return postJson("/forge/validate", { mission });
}

export async function generateForgeCadScript(mission) {
  return postJson("/forge/generate-cad-script", { mission });
}

export async function executeForgeCadScript(scriptPath) {
  return postJson("/forge/execute-cad-script", {
    script_path: scriptPath,
  });
}