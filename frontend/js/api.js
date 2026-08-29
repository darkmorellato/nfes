const API_BASE = window.location.origin;

async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const config = {
        headers: {
            "Content-Type": "application/json",
            ...options.headers,
        },
        ...options,
    };

    try {
        const response = await fetch(url, config);
        const data = await response.json();
        return { success: response.ok, data, status: response.status };
    } catch (error) {
        return { success: false, data: { error: error.message }, status: 0 };
    }
}

async function apiGet(endpoint) {
    return apiRequest(endpoint, { method: "GET" });
}

async function apiPost(endpoint, body) {
    return apiRequest(endpoint, {
        method: "POST",
        body: JSON.stringify(body),
    });
}

async function apiUploadForm(endpoint, formData) {
    const url = `${API_BASE}${endpoint}`;
    try {
        const response = await fetch(url, {
            method: "POST",
            body: formData,
        });
        const data = await response.json();
        return { success: response.ok, data, status: response.status };
    } catch (error) {
        return { success: false, data: { error: error.message }, status: 0 };
    }
}
