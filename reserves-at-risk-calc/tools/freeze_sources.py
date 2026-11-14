"""Freeze the IMF observations and independently calculate the reference answers."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import json
from pathlib import Path
from urllib.request import urlopen
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
COHORTS = {
    "A": dict(zip("AUT BEL DNK GRC PRT ESP NLD FIN SWE".split(), (
        "Austria", "Belgium", "Denmark", "Greece", "Portugal", "Spain",
        "Netherlands", "Finland", "Sweden",
    ))),
    "B": dict(zip("AUS CHE GBR JPN KOR MEX DEU FRA ITA".split(), (
        "Australia", "Switzerland", "United Kingdom", "Japan", "South Korea",
        "Mexico", "Germany", "France", "Italy",
    ))),
}
SPLITS = {
    "train": ("A", 2023), "group_01": ("B", 2023),
    "group_02": ("A", 2025), "group_03": ("B", 2025),
}
INDICATORS = {
    "value": "IRFCLDT1_IRFCL56_USD",
    "volume": "IRFCLDT1_IRFCL56V_FTO",
    "total": "IRFCLDT1_IRFCL65_USD",
}
API = "https://api.imf.org/external/sdmx/2.1/data/"
RESERVES_URL = (
    API + "IMF.STA,IRFCL,12.0.0/" + "+".join((*COHORTS["A"], *COHORTS["B"]))
    + "." + "+".join(INDICATORS.values())
    + ".S1XS1311.M?startPeriod=2023-M12&endPeriod=2025-M12"
)
PRICE_URL = API + "IMF.RES,PCPS,9.0.0/G001.PGOLD.USD.M?startPeriod=2022-09&endPeriod=2025-09"


def read_observations(url):
    with urlopen(url, timeout=35) as response:
        document = ElementTree.fromstring(response.read())
    for series in document.iter():
        if series.tag.rsplit("}", 1)[-1] == "Series":
            for obs in series:
                if obs.get("OBS_VALUE") is not None:
                    yield series.attrib, obs.attrib["TIME_PERIOD"].replace("-M", "-"), Decimal(obs.attrib["OBS_VALUE"])


def capture():
    reserves = {}
    for series, date, value in read_observations(RESERVES_URL):
        if date in {"2023-12", "2025-12"}:
            key = series["COUNTRY"], series["INDICATOR"], date
            if key in reserves:
                raise ValueError(f"Duplicate reserve observation {key}")
            reserves[key] = value / 1_000_000
    gold = {}
    for _, date, value in read_observations(PRICE_URL):
        if date in gold or not value.is_finite() or value <= 0:
            raise ValueError(f"Invalid gold price observation {date}")
        gold[date] = value
    prices = {}
    for year in (2023, 2025):
        months = [f"{year - 1}-{m:02d}" for m in (9, 10, 11, 12)]
        months.extend(f"{year}-{m:02d}" for m in range(1, 10))
        prices[str(year)] = {month: str(gold[month]) for month in months}

    panels = {}
    for split, (cohort, year) in SPLITS.items():
        countries = []
        for index, (code, name) in enumerate(COHORTS[cohort].items()):
            fields = []
            if index < 8:
                fields.append("value")
            if index < 7:
                fields.append("total")
            if index in (0, 1, 8):
                fields.append("volume")
            record = {"country": name, "code": code}
            for field in fields:
                amount = reserves[code, INDICATORS[field], f"{year}-12"]
                if not amount.is_finite() or amount <= 0:
                    raise ValueError(f"Invalid observation for {code}, {year}, {field}")
                record[field] = str(amount)
            countries.append(record)
        panels[split] = {"cohort": cohort, "year": year, "countries": countries}
    return {
        "captured_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pcps": PRICE_URL, "irfcl": RESERVES_URL,
        "prices_usd_per_troy_ounce": prices, "panels": panels,
    }


def reference(prices, countries):
    with localcontext() as ctx:
        ctx.prec = 40
        amounts = list(map(Decimal, prices))
        returns = [(b / a).ln() * 100 for a, b in zip(amounts, amounts[1:])]

        def stdev(samples):
            mean = sum(samples) / len(samples)
            return (sum((x - mean) ** 2 for x in samples) / (len(samples) - 1)).sqrt()

        z, vol3 = Decimal("1.65"), stdev(returns[-3:])
        mean_price = sum(amounts[-9:]) / 9
        step1 = dict(zip(("C3", "C4", "C5", "C6"), map(float, (
            z, vol3, vol3 * Decimal(12).sqrt(), stdev(returns),
        ))))
        step2, step3 = {}, {}
        for row in countries:
            gold = Decimal(row["value"]) if "value" in row else Decimal(row["volume"]) * mean_price
            exposure = gold * z * vol3 / 100
            step2[row["country"]] = {"gold_value": float(gold), "exposure": float(exposure)}
            if "total" in row:
                total = Decimal(row["total"])
                step3[row["country"]] = {
                    "gold_value": float(gold), "total_reserves": float(total),
                    "rar_percent": float(100 * exposure / total),
                }
        return {"step1": step1, "step2": step2, "step3": step3}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="store_true", help="Fetch the public IMF observations once")
    args = parser.parse_args()
    snapshot = ROOT / "source/snapshot.json"
    if args.capture:
        if snapshot.exists():
            raise SystemExit("The snapshot is already frozen")
        write_json(snapshot, capture())
    source = json.loads(snapshot.read_text(encoding="utf-8"))
    for split, panel in source["panels"].items():
        target = ROOT if split == "train" else ROOT / f"evaluation/{split}"
        prices = source["prices_usd_per_troy_ounce"][str(panel["year"])]
        write_json(target / "verifier/expected_output.json", reference(prices.values(), panel["countries"]))
        print(f"{split}: {panel['year']} {panel['cohort']}, 43 reference items")


if __name__ == "__main__":
    main()
