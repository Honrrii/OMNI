const API_BASE_URL = "http://127.0.0.1:8000";

export async function getRosStatus() {
  const response = await fetch(`${API_BASE_URL}/ros/status`);

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.detail || "ROS status request failed.");
  }

  return data;
}