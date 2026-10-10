(() => {
    const form = document.querySelector("form[data-auto-confirm]");
    if (!form) return;
    const result = document.getElementById("acknowledgement-result");
    const button = form.querySelector("button");
    let attempted = false;

    const confirm = async () => {
        button.disabled = true;
        result.textContent = "Recording that the Technical Team has seen this submission…";
        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: new FormData(form),
                credentials: "same-origin",
                redirect: "error",
            });
            if (response.status !== 204) throw new Error("Confirmation failed");
            window.location.reload();
        } catch {
            result.textContent = "Confirmation could not be recorded. Select Retry confirmation to try again.";
            button.textContent = "Retry confirmation";
            button.disabled = false;
        }
    };
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        confirm();
    });
    const confirmWhenVisible = () => {
        if (document.visibilityState === "visible" && !attempted) {
            attempted = true;
            confirm();
        }
    };
    document.addEventListener("visibilitychange", confirmWhenVisible);
    confirmWhenVisible();
})();
