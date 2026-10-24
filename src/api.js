function getErrorMessage(data, status) {
  if (typeof data?.detail === 'string') {
    return data.detail;
  }

  if (data && typeof data === 'object' && !Array.isArray(data)) {
    const messages = Object.entries(data).map(([field, errors]) => {
      const text = Array.isArray(errors)
        ? errors.join(' ')
        : String(errors);

      if (field === 'non_field_errors' || field === 'detail') {
        return text;
      }

      const label = field === 'confirmPassword' ? 'Confirm password' : field;
      return `${label}: ${text}`;
    });

    if (messages.length > 0) {
      return messages.join('\n');
    }
  }

  return `Request failed (HTTP ${status}).`;
}

async function request(url, options = {}) {
  let response;
  const controller = new AbortController();
  const abort = () => controller.abort();
  options.signal?.addEventListener('abort', abort, { once: true });
  if (options.signal?.aborted) controller.abort();
  const timeout = setTimeout(abort, 15000);

  try {
    response = await fetch(url, {
      ...options,
      signal: controller.signal,
      credentials: 'same-origin',
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
        ...options.headers,
      },
    });
  } catch {
    throw new Error(
      'Unable to reach the server. Check that Django and Vite are running.'
    );
  } finally {
    clearTimeout(timeout);
    options.signal?.removeEventListener('abort', abort);
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const error = new Error(
      getErrorMessage(data, response.status)
    );

    error.status = response.status;
    throw error;
  }

  if (data === null) {
    throw new Error('Expected a JSON response from the backend.');
  }

  return data;
}

async function post(url, body = {}) {
  const { csrfToken } = await request('/api/auth/csrf/');

  if (!csrfToken) {
    throw new Error('The backend did not return a CSRF token.');
  }

  return request(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken,
    },
    body: JSON.stringify(body),
  });
}

export async function loginUser(email, password) {
  const data = await post('/api/auth/login/', {
    email,
    password,
  });

  return data.user;
}

export async function registerUser(details) {
  return post('/api/auth/register/', details);
}

export async function getCurrentUser(options = {}) {
  try {
    const data = await request('/api/auth/me/', options);

    if (!data.user) {
      throw new Error('The backend did not return the current user.');
    }

    return data.user;
  } catch (error) {
    if (error.status === 401 || error.status === 403) {
      return null;
    }

    throw error;
  }
}

export async function logoutUser() {
  try {
    await post('/api/auth/logout/');
  } catch (error) {
    if (error.status === 401 || error.status === 403) {
      const currentUser = await getCurrentUser();

      if (currentUser === null) {
        return;
      }
    }

    throw error;
  }
}

export async function getRooms({ date, time, zone, capacity, facilities = [], category, status } = {}, options = {}) {
  const query = new URLSearchParams();

  for (const [name, value] of Object.entries({ date, time, zone, capacity, category, status })) {
    if (value && value !== 'all') query.set(name, value);
  }
  for (const facility of facilities) query.append('facilities', facility);

  const queryString = query.toString();
  const url = queryString
    ? `/api/rooms/?${queryString}`
    : '/api/rooms/';

  const data = await request(url, options);

  if (!Array.isArray(data)) {
    throw new Error('Expected a room list from the backend.');
  }

  return data;
}

export function getRoomFilterOptions(options = {}) {
  return request('/api/rooms/filters/', options);
}

export async function getCampusSchedule(date, options = {}) {
  const query = date ? `?${new URLSearchParams({ date })}` : '';
  const data = await request(`/api/schedules/${query}`, options);
  if (!Array.isArray(data)) throw new Error('Expected a schedule list from the backend.');
  return data;
}

export function getLagosDateTime() {
  const formatter = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Africa/Lagos',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  });

  const parts = {};

  for (const part of formatter.formatToParts(new Date())) {
    parts[part.type] = part.value;
  }

  return {
    date: `${parts.year}-${parts.month}-${parts.day}`,
    time: `${parts.hour}:${parts.minute}`,
  };
}

