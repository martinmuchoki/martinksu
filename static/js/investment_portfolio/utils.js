window.MIPPortfolio = window.MIPPortfolio || {};

window.MIPPortfolio.utils = (() => {
    "use strict";

    function toNumber(value, fallback = 0) {
        const parsed = Number.parseFloat(value);

        return Number.isFinite(parsed)
            ? parsed
            : fallback;
    }

    function toInteger(value, fallback = 0) {
        const parsed = Number.parseInt(value, 10);

        return Number.isFinite(parsed)
            ? parsed
            : fallback;
    }

    function roundMoney(value) {
        return Math.round(
            (toNumber(value) + Number.EPSILON) * 100
        ) / 100;
    }

    function getCurrencyCode() {
        const currencyInput = document.getElementById(
            "setting-currency"
        );

        return currencyInput?.value || "KES";
    }

    function formatMoney(value, currencyCode = null) {
        const currency = currencyCode || getCurrencyCode();
        const amount = toNumber(value);

        try {
            return new Intl.NumberFormat("en-KE", {
                style: "currency",
                currency,
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            }).format(amount);
        } catch (error) {
            return `${currency} ${amount.toFixed(2)}`;
        }
    }

    function parseSettlementDays(value) {
        const match = String(value || "").match(
            /^T\+(\d+)$/i
        );

        if (!match) {
            return 0;
        }

        return toInteger(match[1], 0);
    }

    function parseDateInput(value) {
        if (!value) {
            return null;
        }

        const parts = String(value)
            .split("-")
            .map((part) => toInteger(part));

        if (parts.length !== 3) {
            return null;
        }

        const [year, month, day] = parts;

        const date = new Date(
            year,
            month - 1,
            day,
            12,
            0,
            0,
            0
        );

        if (Number.isNaN(date.getTime())) {
            return null;
        }

        return date;
    }

    function formatDateInput(date) {
        if (!(date instanceof Date)) {
            return "";
        }

        const year = date.getFullYear();
        const month = String(
            date.getMonth() + 1
        ).padStart(2, "0");
        const day = String(
            date.getDate()
        ).padStart(2, "0");

        return `${year}-${month}-${day}`;
    }

    function isWeekend(date) {
        const day = date.getDay();

        return day === 0 || day === 6;
    }

    function dispatchPortfolioEvent(
        eventName,
        detail = {}
    ) {
        document.dispatchEvent(
            new CustomEvent(eventName, {
                detail,
            })
        );
    }

    return {
        toNumber,
        toInteger,
        roundMoney,
        getCurrencyCode,
        formatMoney,
        parseSettlementDays,
        parseDateInput,
        formatDateInput,
        isWeekend,
        dispatchPortfolioEvent,
    };
})();
