window.MIPPortfolio = window.MIPPortfolio || {};

window.MIPPortfolio.settlement = (() => {
    "use strict";

    const utils = window.MIPPortfolio.utils;

    function addBusinessDays(date, businessDays) {
        const result = new Date(date);
        let remaining = Math.max(
            0,
            utils.toInteger(businessDays)
        );

        while (remaining > 0) {
            result.setDate(result.getDate() + 1);

            if (!utils.isWeekend(result)) {
                remaining -= 1;
            }
        }

        return result;
    }

    function calculateSettlementDate(
        tradeDateValue,
        settlementRule
    ) {
        const tradeDate = utils.parseDateInput(
            tradeDateValue
        );

        if (!tradeDate) {
            return "";
        }

        const businessDays =
            utils.parseSettlementDays(
                settlementRule
            );

        const settlementDate = addBusinessDays(
            tradeDate,
            businessDays
        );

        return utils.formatDateInput(
            settlementDate
        );
    }

    function updateSettlementDate() {
        const tradeDateInput =
            document.getElementById("trade-date");

        const settlementDateInput =
            document.getElementById(
                "settlement-date"
            );

        const settlementRuleInput =
            document.getElementById(
                "setting-settlement"
            );

        if (
            !tradeDateInput ||
            !settlementDateInput ||
            !settlementRuleInput
        ) {
            return;
        }

        settlementDateInput.value =
            calculateSettlementDate(
                tradeDateInput.value,
                settlementRuleInput.value
            );
    }

    return {
        addBusinessDays,
        calculateSettlementDate,
        updateSettlementDate,
    };
})();
