window.MIPPortfolio = window.MIPPortfolio || {};

window.MIPPortfolio.calculations = (() => {
    "use strict";

    const utils = window.MIPPortfolio.utils;

    function readTradeSide() {
        return (
            document.querySelector(
                'input[name="side"]:checked'
            )?.value || "BUY"
        ).toUpperCase();
    }

    function readCalculationSettings() {
        const chargeRate = utils.toNumber(
            document.getElementById(
                "setting-charge-rate"
            )?.value,
            0
        );

        const autoCalculate =
            document.getElementById(
                "setting-auto-calculate"
            )?.value !== "0";

        const manualOverride =
            document.getElementById(
                "setting-manual-override"
            )?.value === "1";

        return {
            chargeRate,
            autoCalculate,
            manualOverride,
        };
    }

    function calculateTrade({
        quantity,
        price,
        side,
        submittedCharges,
        chargeRate,
        autoCalculate,
        manualOverride,
    }) {
        const safeQuantity = Math.max(
            0,
            utils.toNumber(quantity)
        );

        const safePrice = Math.max(
            0,
            utils.toNumber(price)
        );

        const gross = utils.roundMoney(
            safeQuantity * safePrice
        );

        let charges = Math.max(
            0,
            utils.toNumber(submittedCharges)
        );

        if (autoCalculate && !manualOverride) {
            charges = utils.roundMoney(
                gross * (chargeRate / 100)
            );
        }

        const normalizedSide = String(
            side || "BUY"
        ).toUpperCase();

        const net = normalizedSide === "SELL"
            ? utils.roundMoney(
                Math.max(0, gross - charges)
            )
            : utils.roundMoney(gross + charges);

        return {
            quantity: safeQuantity,
            price: safePrice,
            side: normalizedSide,
            gross,
            charges,
            net,
        };
    }

    function calculateFromForm() {
        const settings = readCalculationSettings();

        return calculateTrade({
            quantity:
                document.getElementById(
                    "trade-quantity"
                )?.value,
            price:
                document.getElementById(
                    "trade-price"
                )?.value,
            side: readTradeSide(),
            submittedCharges:
                document.getElementById(
                    "trade-charges"
                )?.value,
            ...settings,
        });
    }

    return {
        readTradeSide,
        readCalculationSettings,
        calculateTrade,
        calculateFromForm,
    };
})();
