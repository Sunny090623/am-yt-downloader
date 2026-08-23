const BASE_URL = '';

export async function fetchAuthStatus() {
  const res = await fetch(`${BASE_URL}/api/auth/status`, {
    credentials: 'include'
  });
  if (!res.ok) throw new Error('获取认证状态失败');
  return res.json();
}

export async function adminLogin(password) {
  const res = await fetch(`${BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
    credentials: 'include'
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '管理员登录失败');
  return data;
}

export async function adminLogout() {
  const res = await fetch(`${BASE_URL}/api/auth/logout`, {
    method: 'POST',
    credentials: 'include'
  });
  if (!res.ok) throw new Error('退出登录失败');
  return res.json();
}

export async function fetchTasks() {
  const res = await fetch(`${BASE_URL}/api/tasks`, {
    credentials: 'include'
  });
  if (!res.ok) throw new Error('获取任务列表失败');
  return res.json();
}

export async function createDownloadTask(url, serviceType = 'youtube') {
  const res = await fetch(`${BASE_URL}/api/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, service_type: serviceType }),
    credentials: 'include'
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '提交下载任务失败');
  return data;
}

export async function cancelDownloadTask(taskId) {
  const res = await fetch(`${BASE_URL}/api/tasks/${taskId}/cancel`, {
    method: 'POST',
    credentials: 'include'
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '取消任务失败');
  return data;
}

export async function deleteTask(taskId) {
  const res = await fetch(`${BASE_URL}/api/tasks/${taskId}`, {
    method: 'DELETE',
    credentials: 'include'
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '删除任务失败');
  return data;
}

export async function clearFinishedTasks() {
  const res = await fetch(`${BASE_URL}/api/tasks/clear-finished`, {
    method: 'POST',
    credentials: 'include'
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '一键清除任务失败');
  return data;
}

export async function fetchAdminStats() {
  const res = await fetch(`${BASE_URL}/api/admin/stats`, {
    credentials: 'include'
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '获取系统诊断信息失败');
  return data;
}

export async function triggerManualCleanup() {
  const res = await fetch(`${BASE_URL}/api/admin/cleanup`, {
    method: 'POST',
    credentials: 'include'
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '执行清理失败');
  return data;
}

export async function deleteAdminTask(taskId) {
  const res = await fetch(`${BASE_URL}/api/admin/tasks/${taskId}`, {
    method: 'DELETE',
    credentials: 'include'
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '删除任务失败');
  return data;
}

export async function fetchAdminLogs() {
  const res = await fetch(`${BASE_URL}/api/admin/logs`, {
    credentials: 'include'
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '获取运行日志失败');
  return data.logs;
}

export function subscribeToTaskEvents(onTaskUpdate) {
  const eventSource = new EventSource(`${BASE_URL}/api/tasks/events`, {
    withCredentials: true
  });

  eventSource.addEventListener('task_update', (event) => {
    try {
      const data = JSON.parse(event.data);
      onTaskUpdate(data);
    } catch (e) {
      console.error('Failed to parse SSE task update', e);
    }
  });

  eventSource.onerror = (err) => {
    console.warn('SSE connection error, browser will auto reconnect', err);
  };

  return () => {
    eventSource.close();
  };
}
