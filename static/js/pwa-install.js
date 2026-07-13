let deferredInstallPrompt = null;

const installButton = document.getElementById(
    "install-mip-pro"
);

window.addEventListener(
    "beforeinstallprompt",
    event => {
        event.preventDefault();
        deferredInstallPrompt = event;

        if (installButton) {
            installButton.hidden = false;
        }
    }
);

if (installButton) {
    installButton.addEventListener(
        "click",
        async () => {
            if (!deferredInstallPrompt) {
                alert(
                    "Install is not available yet. " +
                    "Open MIP PRO using HTTPS in Chrome."
                );
                return;
            }

            deferredInstallPrompt.prompt();

            const choice =
                await deferredInstallPrompt.userChoice;

            console.log(
                "MIP PRO install choice:",
                choice.outcome
            );

            deferredInstallPrompt = null;
            installButton.hidden = true;
        }
    );
}

window.addEventListener(
    "appinstalled",
    () => {
        deferredInstallPrompt = null;

        if (installButton) {
            installButton.hidden = true;
        }

        console.log(
            "MIP PRO installed successfully."
        );
    }
);

if ("serviceWorker" in navigator) {
    navigator.serviceWorker.addEventListener(
        "controllerchange",
        () => {
            if (sessionStorage.getItem(
                "mip-pro-update-reloaded"
            )) {
                return;
            }

            sessionStorage.setItem(
                "mip-pro-update-reloaded",
                "1"
            );

            window.location.reload();
        }
    );
}
