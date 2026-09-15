const ML_ROOT = `${import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"}/api/ml`;
export const imageUrl = (id, artifact = "thumbnail") =>
  `${ML_ROOT}/v2/images/${id}/${artifact}`;

export async function mlRequest(path, options = {}) {
  const response = await fetch(`${ML_ROOT}${path}`, options);
  const data = await response.json();
  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail
          .map((item) => `${item.loc?.slice(1).join(".")}: ${item.msg}`)
          .join("; ")
      : data.detail;
    throw new Error(detail || `OMNITorch request failed (${response.status}).`);
  }
  return data;
}
export const postML = (path, data) =>
  mlRequest(`/v2/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
export const uploadImage = (file) =>
  mlRequest("/v2/images", {
    method: "POST",
    headers: {
      "Content-Type": file.type,
      "X-Image-Name": encodeURIComponent(file.name),
    },
    body: file,
  });
