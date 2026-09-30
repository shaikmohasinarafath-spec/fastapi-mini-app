const API_URL = "http://127.0.0.1:8000";

const loginForm = document.getElementById("loginForm");

loginForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;
    const message = document.getElementById("message");

    try {
        const formData = new URLSearchParams();

        formData.append("username", username);
        formData.append("password", password);

        const response = await fetch(`${API_URL}/auth/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body: formData
        });

        console.log("STATUS:", response.status);

        const data = await response.json();

        console.log("RESPONSE:", data);

        if (!response.ok) {
            message.textContent = JSON.stringify(data.detail || data);
            return;
        }

        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("username", username);

        message.textContent = "Login successful!";

        window.location.href = "dashboard.html";

    } catch (error) {
        console.error("FULL ERROR:", error);
        message.textContent = "CONNECTION ERROR: " + error.message;
    }
});