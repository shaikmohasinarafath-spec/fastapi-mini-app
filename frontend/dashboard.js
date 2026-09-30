const API_URL = "http://127.0.0.1:8000";

let materialId = null;

async function uploadPDF() {
    const fileInput = document.getElementById("pdfFile");
    const message = document.getElementById("uploadMessage");

    if (!fileInput.files.length) {
        message.textContent = "Please select a PDF file.";
        return;
    }

    const token = localStorage.getItem("access_token");

    if (!token) {
        message.textContent = "Please login again.";
        window.location.href = "index.html";
        return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    try {
        const response = await fetch(`${API_URL}/materials/upload`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`
            },
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            message.textContent = JSON.stringify(data.detail || data);
            return;
        }

        materialId = data.material_id;

        localStorage.setItem("material_id", materialId);

        message.textContent =
            `Upload successful! Material ID: ${materialId}`;

    } catch (error) {
        message.textContent =
            "Connection error: " + error.message;
    }
}

async function generateSummary() {
    const result = document.getElementById("result");
    const token = localStorage.getItem("access_token");

    materialId = localStorage.getItem("material_id");

    if (!materialId) {
        result.textContent = "Please upload a PDF first.";
        return;
    }

    try {
        const response = await fetch(
            `${API_URL}/materials/${materialId}/summary`,
            {
                method: "POST",
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            }
        );

        const data = await response.json();

        if (!response.ok) {
            result.textContent = JSON.stringify(data.detail || data);
            return;
        }

        result.innerHTML =
            `<h3>Summary</h3><p>${data.summary}</p>`;

    } catch (error) {
        result.textContent =
            "Connection error: " + error.message;
    }
}

async function generateQuiz() {
    const result = document.getElementById("result");
    const token = localStorage.getItem("access_token");

    materialId = localStorage.getItem("material_id");

    if (!materialId) {
        result.textContent = "Please upload a PDF first.";
        return;
    }

    try {
        const response = await fetch(
            `${API_URL}/materials/${materialId}/quiz`,
            {
                method: "POST",
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            }
        );

        const data = await response.json();

        if (!response.ok) {
            result.textContent = JSON.stringify(data.detail || data);
            return;
        }

        let html = "<h3>Quiz</h3>";

        data.quiz.forEach((item, index) => {
            html += `
                <div>
                    <p>
                        <strong>Q${index + 1}:</strong>
                        ${item.question}
                    </p>
                    <p>
                        <strong>Answer:</strong>
                        ${item.answer}
                    </p>
                </div>
                <hr>
            `;
        });

        result.innerHTML = html;

    } catch (error) {
        result.textContent =
            "Connection error: " + error.message;
    }
}

function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("username");
    localStorage.removeItem("material_id");

    window.location.href = "index.html";
}