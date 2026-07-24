window.MIPPortfolio = window.MIPPortfolio || {};

window.MIPPortfolio.main = (() => {
    "use strict";

    const ui = window.MIPPortfolio.ui;
    const settlement =
        window.MIPPortfolio.settlement;

    function bindInput(
        selector,
        eventName,
        callback
    ) {
        document.querySelectorAll(selector)
            .forEach((element) => {
                element.addEventListener(
                    eventName,
                    callback
                );
            });
    }

    function refreshTradeForm() {
        settlement.updateSettlementDate();
        ui.updateCalculatedFields();
    }

    function bindCalculationEvents() {
        [
            "#trade-quantity",
            "#trade-price",
            "#trade-charges",
            "#setting-charge-rate",
        ].forEach((selector) => {
            bindInput(
                selector,
                "input",
                ui.updateCalculatedFields
            );
        });

        [
            "#setting-auto-calculate",
            "#setting-manual-override",
            "#setting-currency",
        ].forEach((selector) => {
            bindInput(
                selector,
                "change",
                ui.updateCalculatedFields
            );
        });

        bindInput(
            'input[name="side"]',
            "change",
            ui.updateCalculatedFields
        );
    }

    function bindSettlementEvents() {
        bindInput(
            "#trade-date",
            "change",
            settlement.updateSettlementDate
        );

        bindInput(
            "#setting-settlement",
            "change",
            settlement.updateSettlementDate
        );
    }

    function bindFormSubmission() {
        const form = document.getElementById(
            "investment-trade-form"
        );

        if (!form) {
            return;
        }

        form.addEventListener(
            "submit",
            ui.validateTradeForm
        );
    }

    function bindSymbolNormalization() {
        const symbolInput = document.querySelector(
            'input[name="symbol"]'
        );

        if (!symbolInput) {
            return;
        }

        symbolInput.addEventListener(
            "blur",
            ui.normalizeSymbol
        );
    }

    function init() {
        bindCalculationEvents();
        bindSettlementEvents();
        bindFormSubmission();
        bindSymbolNormalization();
        refreshTradeForm();
    }

    document.addEventListener(
        "DOMContentLoaded",
        init
    );

    return {
        init,
        refreshTradeForm,
    };
})();

/* Stock symbol and company dropdown synchronization */
document.addEventListener("DOMContentLoaded", () => {
    const symbolSelect =
        document.getElementById("trade-symbol");

    const companySelect =
        document.getElementById("trade-company-name");

    if (!symbolSelect || !companySelect) {
        return;
    }

    symbolSelect.addEventListener("change", () => {
        const selectedOption =
            symbolSelect.options[
                symbolSelect.selectedIndex
            ];

        const company =
            selectedOption?.dataset.company || "";

        companySelect.value = company;
    });

    companySelect.addEventListener("change", () => {
        const selectedOption =
            companySelect.options[
                companySelect.selectedIndex
            ];

        const symbol =
            selectedOption?.dataset.symbol || "";

        symbolSelect.value = symbol;
    });
});
