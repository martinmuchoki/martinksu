if ("serviceWorker" in navigator) {

    window.addEventListener("load", () => {

        navigator.serviceWorker
            .register("/service-worker.js")

            .then(registration => {

                console.log(
                    "MIP PRO Service Worker registered",
                    registration.scope
                );

            })

            .catch(error => {

                console.error(
                    "Service Worker failed",
                    error
                );

            });

    });

}
