export function mapCountryFraud(report) {

    const result = {};

    if (!report?.country) {

        return result;

    }

    report.country.forEach(item => {

        const stateId = item.regionId;

        result[stateId] = {

            risk: item.risk_level

        };

    });

    return result;

}