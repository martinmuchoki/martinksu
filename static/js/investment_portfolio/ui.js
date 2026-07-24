window.MIPPortfolio = window.MIPPortfolio || {};

window.MIPPortfolio.ui = (() => {
    "use strict";

    const utils = window.MIPPortfolio.utils;
    const calculations =
        window.MIPPortfolio.calculations;

    function getElement(id) {
        return document.getElementById(id);
    }

    function setInputValue(id, value) {
        const element = getElement(id);

        if (!element) {
            return;
        }

        element.value = Number.isFinite(value)
            ? value.toFixed(2)
            : "0.00";
    }

    function setText(id, value) {
        const element = getElement(id);

        if (element) {
            element.textContent = value;
        }
    }

    function updateChargeInputState() {
        const chargeInput =
            getElement("trade-charges");

        const settings =
            calculations.readCalculationSettings();

        if (!chargeInput) {
            return;
        }

        const managedAutomatically =
            settings.autoCalculate &&
            !settings.manualOverride;

        chargeInput.readOnly = managedAutomatically;

        chargeInput.title = managedAutomatically
            ? "Charges are calculated automatically from the saved rate."
            : "Charges may be entered manually.";
    }

    function updateTradeButton(side) {
        const button =
            getElement("save-trade-button");

        if (!button) {
            return;
        }

        button.textContent =
            `Save ${side} Trade`;

        button.dataset.side = side;
    }

    function updatePreview(result) {
        const currency = utils.getCurrencyCode();

        setText(
            "preview-gross",
            utils.formatMoney(
                result.gross,
                currency
            )
        );

        setText(
            "preview-charges",
            utils.formatMoney(
                result.charges,
                currency
            )
        );

        setText(
            "preview-net",
            utils.formatMoney(
                result.net,
                currency
            )
        );
    }

    function updateCalculatedFields() {
        const result =
            calculations.calculateFromForm();

        setInputValue(
            "gross-amount",
            result.gross
        );

        const settings =
            calculations.readCalculationSettings();

        if (
            settings.autoCalculate &&
            !settings.manualOverride
        ) {
            setInputValue(
                "trade-charges",
                result.charges
            );
        }

        setInputValue(
            "net-amount",
            result.net
        );

        updateTradeButton(result.side);
        updatePreview(result);
        updateChargeInputState();

        utils.dispatchPortfolioEvent(
            "mip:trade-calculated",
            result
        );

        return result;
    }

    function normalizeSymbol() {
        const symbolInput = document.querySelector(
            'input[name="symbol"]'
        );

        if (!symbolInput) {
            return;
        }

        symbolInput.value = symbolInput.value
            .trim()
            .toUpperCase();
    }

    function validateTradeForm(event) {
        const result =
            updateCalculatedFields();

        if (
            result.quantity <= 0 ||
            result.price <= 0
        ) {
            event.preventDefault();

            window.alert(
                "Enter a valid number of shares and executed price."
            );

            return false;
        }

        normalizeSymbol();

        return true;
    }

    return {
        updateChargeInputState,
        updateTradeButton,
        updatePreview,
        updateCalculatedFields,
        normalizeSymbol,
        validateTradeForm,
    };
})();
