// Exports the synthetic demo book so the Python core and agents use exactly the same data.
import { writeFileSync } from "node:fs";

import * as demo from "../src/data/demo";

const book = {
  _note: "Synthetic demo book. All people, firm and fund names are fictional; weights and prices are invented.",
  today: demo.TODAY,
  fy_label: demo.FY_LABEL,
  ltcg_exemption: demo.LTCG_EXEMPTION,
  ltcg_rate: demo.LTCG_RATE,
  stcg_rate: demo.STCG_RATE,
  disclosure_month: demo.DISCLOSURE_MONTH,
  source_as_of: demo.sourceAsOf,
  models: demo.models,
  stocks: demo.stocks,
  funds: demo.funds,
  clients: demo.clientSpecs,
  primary_adviser: demo.primaryAdviser,
};
writeFileSync("../data/synthetic/book.json", JSON.stringify(book, null, 1) + "\n");
console.log(`exported ${book.clients.length} clients, ${Object.keys(book.funds).length} funds`);
