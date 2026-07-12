async function refreshControlCenter() {
    const button = document.getElementById(
        "refresh-control-center"
    );

    if (button) {
        button.disabled = true;
        button.textContent = "Refreshing...";
    }

    try {
        const response = await fetch(
            "/api/v11.6.1/control-center",
            {
                headers: {
                    "Accept": "application/json"
                }
            }
        );

        if (!response.ok) {
            throw new Error(
                `Control Center API returned ${response.status}`
            );
        }

        await response.json();

        window.location.reload();
    } catch (error) {
        console.error(error);
        alert(
            "Unable to refresh the Control Center. " +
            "Please check the application logs."
        );
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = "Refresh Status";
        }
    }
}

document.addEventListener(
    "DOMContentLoaded",
    () => {
        const button = document.getElementById(
            "refresh-control-center"
        );

        if (button) {
            button.addEventListener(
                "click",
                refreshControlCenter
            );
        }
    }
);
