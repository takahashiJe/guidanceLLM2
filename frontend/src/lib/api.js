const API_BASE = '/back';

export async function createPlan(payload) {
  const r = await fetch(`${API_BASE}/api/nav/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(`plan create failed: ${r.status}`);
  return r.json(); // {task_id,status}
}

export async function fetchPlanTask(taskId) {
  const r = await fetch(`${API_BASE}/api/nav/plan/tasks/${taskId}`, {
    headers: { 'Accept': 'application/json' },
  });
  // 200=完成, 202=進行中, 500=失敗
  return { status: r.status, body: r.status === 200 ? await r.json() : await r.json().catch(() => ({})) };
}
