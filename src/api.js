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

      return `${field}: ${text}`;
    });

    if (messages.length > 0) {
      return messages.join('\n');
    }
  }

  return `Request failed (HTTP ${status}).`;
}

async function request(url, options = {}) {
  let response;

  try {
    response = await fetch(url, {
      ...options,
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

export async function getCurrentUser() {
  try {
    const data = await request('/api/auth/me/');

    if (!data.user) {
      throw new Error('The backend did not return the current user.');
    }

    return data.user;
  } catch (error) {
    // This endpoint requires authentication.
    // An anonymous or expired session is not a connection failure.
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
      // The session might already have expired.
      // Do not mistake a CSRF failure for successful logout:
      // first confirm that no authenticated session remains.
      const currentUser = await getCurrentUser();

      if (currentUser === null) {
        return;
      }
    }

    throw error;
  }
}

