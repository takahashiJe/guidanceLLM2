import axios from "axios";
const api = axios.create({ baseURL: "/api" });

// /api/nav/plan を叩く
export async function createPlan(req) {
  const { data } = await api.post("/nav/plan", req);
  return data;
}
