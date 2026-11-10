import { mkdir, readFile, unlink, writeFile } from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [root, validationDir] = process.argv.slice(2);
const source = JSON.parse(await readFile(path.join(root, "source/snapshot.json"), "utf8"));
const template = path.join(root, "diagnosis/inputs/test-rar.xlsx");
const open = async (file) => SpreadsheetFile.importXlsx(await FileBlob.load(file));
async function save(book, file) {
  await (await SpreadsheetFile.exportXlsx(book)).save(file);
  try {
    await unlink(`${file}.inspect.ndjson`);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
}
const column = (index) => String.fromCharCode(67 + index);
const monthLabel = (period) => period.replace(/-0?/, "M");
const sheets = [
  ["Value", "value", "Monetary gold (millions of USD)", "R"],
  ["Volume", "volume", "Monetary gold (millions of fine troy ounces)", "L"],
  ["Total Reserves", "total", "Official reserve assets (millions of USD)", "P"],
];

async function createInputs(panel, prices, target, preview) {
  const book = await open(template);
  const gold = book.worksheets.getItem("Gold price");
  gold.getRange("A2:E430").clear({ applyTo: "contents" });
  gold.getRange("A2:A14").values = Object.keys(prices).map((period) => [monthLabel(period)]);
  gold.getRange("B:B").format.columnWidth = 38;
  gold.getRange("C:E").format.columnWidth = 22;
  gold.getRange("B1:E1").format.wrapText = true;
  gold.getRange("1:1").format.rowHeight = 56;

  for (const [name, field, description, last] of sheets) {
    const tab = book.worksheets.getItem(name);
    tab.getRange(`C1:${last}18`).clear({ applyTo: "contents" });
    tab.getRange("A10:B18").clear({ applyTo: "contents" });
    tab.getRange("A18").values = [[String(panel.year)]];
    tab.getRange(`C:${last}`).format.columnWidth = 25;
    tab.getRange(`C1:${last}1`).format.wrapText = true;
    tab.getRange("1:1").format.rowHeight = 48;
    const observations = panel.countries.filter((country) => field in country);
    for (const [i, country] of observations.entries()) {
      const col = column(i);
      tab.getRange(`${col}1:${col}5`).values = [
        [`${country.country}: ${description}`],
        [`${panel.year} <- Dec-${panel.year}`],
        [`${panel.year} <- Dec-${panel.year}`],
        ["IMF IRFCL"],
        ["End of Period"],
      ];
      tab.getRange(`${col}18`).values = [[Number(country[field])]];
      tab.getRange(`${col}18`).setNumberFormat("#,##0.00######");
    }
  }
  await save(book, path.join(target, "test-rar.xlsx"));

  const raw = Workbook.create();
  const external = raw.worksheets.add("External");
  external.getRange("A1:B15").values = [
    ["Commodity", "PGOLD"],
    ["Commodity.Description", "Gold, US dollars per fine troy ounce"],
    ...Object.entries(prices).map(([period, price]) => [monthLabel(period), Number(price)]),
  ];
  external.getRange("A:A").format.columnWidth = 24;
  external.getRange("B:B").format.columnWidth = 42;
  external.getRange("B3:B15").setNumberFormat("0.00");
  await save(raw, path.join(target, "gold-prices.xlsx"));
  if (preview) {
    for (const [workbook, sheet, range] of [
      [book, "Answer", "A1:K24"],
      [book, "Gold price", "A1:E14"],
      [book, "Value", "A1:J18"],
      [book, "Volume", "A1:E18"],
      [book, "Total Reserves", "A1:I18"],
      [raw, "External", "A1:B15"],
    ]) {
      const blob = await workbook.render({ sheetName: sheet, range, scale: 1 });
      await writeFile(path.join(validationDir, `${sheet}.png`), new Uint8Array(await blob.arrayBuffer()));
    }
  }
}

function reserveColumns(book, name) {
  const headers = book.worksheets.getItem(name).getRange("C1:R1").values[0];
  return new Map(headers.map((value, index) => [
    typeof value === "string" ? value.split(":")[0] : null, column(index),
  ]).filter(([country]) => country !== null));
}

async function createFixture(target, split) {
  // Compute from the exported input workbooks, without reading the reference JSON.
  const book = await open(path.join(target, "test-rar.xlsx"));
  const raw = await open(path.join(target, "gold-prices.xlsx"));
  const price = book.worksheets.getItem("Gold price");
  price.getRange("B2:B14").values = raw.worksheets.getItem("External").getRange("B3:B15").values;
  for (let row = 3; row <= 14; row++) {
    price.getRange(`C${row}`).formulas = [[`=LN(B${row}/B${row - 1})*100`]];
    if (row >= 5) price.getRange(`D${row}`).formulas = [[`=STDEV(C${row - 2}:C${row})`]];
  }
  price.getRange("E14").formulas = [["=STDEV(C3:C14)"]];
  const values = reserveColumns(book, "Value");
  const volumes = reserveColumns(book, "Volume");
  const totals = reserveColumns(book, "Total Reserves");
  const answer = book.worksheets.getItem("Answer");
  answer.getRange("C3").values = [[1.65]];
  answer.getRange("C4:C6").formulas = [["='Gold price'!D14"], ["=C4*SQRT(12)"], ["='Gold price'!E14"]];
  const names = [...values.keys(), ...[...volumes.keys()].filter((name) => !values.has(name))];
  const step2 = new Map();
  for (const [index, name] of names.entries()) {
    const col = column(index);
    step2.set(name, col);
    answer.getRange(`${col}11`).values = [[name]];
    const value = values.has(name)
      ? `=Value!${values.get(name)}18`
      : `=Volume!${volumes.get(name)}18*AVERAGE('Gold price'!B6:B14)`;
    answer.getRange(`${col}12:${col}13`).formulas = [[value], [`=${col}12*$C$3*$C$4/100`]];
  }
  for (const [index, name] of names.filter((name) => totals.has(name)).entries()) {
    const col = column(index);
    answer.getRange(`${col}20`).values = [[name]];
    answer.getRange(`${col}21:${col}24`).formulas = [
      [`=${step2.get(name)}12`],
      [`=${step2.get(name)}13`],
      [`='Total Reserves'!${totals.get(name)}18`],
      [`=${col}22/${col}23*100`],
    ];
  }
  await save(book, path.join(validationDir, `${split}.xlsx`));
  if (split === "train") {
    answer.getRange("C6").formulas = [["='Gold price'!E14+1"]];
    await save(book, path.join(validationDir, "one-wrong.xlsx"));
  }
}

if (validationDir) await mkdir(validationDir, { recursive: true });
for (const [split, panel] of Object.entries(source.panels)) {
  const target = path.join(root, split === "train" ? "environment" : `evaluation/${split}/inputs`);
  await mkdir(target, { recursive: true });
  await createInputs(panel, source.prices_usd_per_troy_ounce[panel.year], target, validationDir && split === "train");
  if (validationDir) await createFixture(target, split);
  console.log(`Built ${split}`);
}
