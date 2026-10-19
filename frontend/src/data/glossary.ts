/** Plain-language glossary used across the console and the "How it works" guide. */

export interface GlossaryEntry {
  term: string;
  full?: string;
  group: "Money and markets" | "Tax" | "People and rules" | "Data and connections" | "Security and privacy" | "Artificial intelligence";
  plain: string;
  example?: string;
}

export const glossary: GlossaryEntry[] = [
  // Money and markets
  { term: "Mutual fund", group: "Money and markets", plain: "A pot of money from many investors that a professional invests in many shares or bonds. You own units of the pot.", example: "₹1 lakh in a fund whose unit price is ₹50 gives you 2,000 units." },
  { term: "NAV", full: "Net Asset Value", group: "Money and markets", plain: "The price of one mutual fund unit on a given day.", example: "Units × NAV = what your holding in that fund is worth." },
  { term: "AMC", full: "Asset Management Company", group: "Money and markets", plain: "The company that runs mutual funds, such as a fund house." },
  { term: "Folio", group: "Money and markets", plain: "Your account number with a fund house. One investor can have several folios." },
  { term: "Demat account", full: "Dematerialised account", group: "Money and markets", plain: "An electronic locker that holds your shares. A broker opens it for you." },
  { term: "Depository", group: "Money and markets", plain: "The national body that keeps every demat locker. India has two: NSDL and CDSL.", example: "Your broker is the front desk; the depository is the vault." },
  { term: "Broker", group: "Money and markets", plain: "The company and app you use to buy and sell shares, such as Dhan or Upstox." },
  { term: "ISIN", full: "International Securities Identification Number", group: "Money and markets", plain: "A 12-character passport number that every share and fund has. It is how we know two records are the same investment.", example: "INE009A01021 is Infosys." },
  { term: "Asset allocation", group: "Money and markets", plain: "How a portfolio is split between equity (shares), debt (bonds), gold and cash." },
  { term: "Model portfolio", group: "Money and markets", plain: "The target split agreed for a client's risk level.", example: "Moderately aggressive: 70% equity, 20% debt, 5% gold, 5% cash." },
  { term: "Drift", group: "Money and markets", plain: "How far the actual split has moved from the target, in percentage points and rupees.", example: "84% equity against a 70% target is +14 points." },
  { term: "Look-through", group: "Money and markets", plain: "Seeing which companies you really own once you open up every fund you hold.", example: "₹2 lakh in a fund that holds 10% HDFC Bank means ₹20,000 of HDFC Bank." },
  { term: "Overlap", group: "Money and markets", plain: "How much two funds hold the same companies. High overlap means paying for two funds that behave like one.", example: "Add the smaller weight of every company both funds hold." },
  { term: "Concentration", group: "Money and markets", plain: "Too much of the portfolio riding on one company once funds are looked through." },
  { term: "Risk profile", group: "Money and markets", plain: "A short assessment of how much risk a client can take, which decides their model portfolio." },

  // Tax
  { term: "FY", full: "Financial year", group: "Tax", plain: "India's tax year, 1 April to 31 March. The Income-tax Act 2025 calls it the tax year.", example: "FY 2026-27 runs from 1 April 2026 to 31 March 2027." },
  { term: "Capital gain", group: "Tax", plain: "Profit from selling an investment for more than you paid." },
  { term: "STCG", full: "Short-term capital gain", group: "Tax", plain: "Profit on listed shares or equity funds held for 12 months or less. Taxed at 20%." },
  { term: "LTCG", full: "Long-term capital gain", group: "Tax", plain: "Profit on listed shares or equity funds held for more than 12 months. Taxed at 12.5%, and the first ₹1.25 lakh each year is tax-free." },
  { term: "Holding period", group: "Tax", plain: "How long you have held an investment. It decides short-term or long-term." },
  { term: "Lot", group: "Tax", plain: "One purchase. Each lot has its own 12-month clock.", example: "A monthly SIP creates 12 lots a year." },
  { term: "Tax-gain harvesting", group: "Tax", plain: "Selling and re-buying to use up the yearly ₹1.25 lakh tax-free long-term gain, so less tax is due later." },
  { term: "ELSS", full: "Equity Linked Savings Scheme", group: "Tax", plain: "A tax-saving equity fund (under the old tax regime) with a 3-year lock-in for each investment." },
  { term: "SIP", full: "Systematic Investment Plan", group: "Tax", plain: "Investing a fixed amount in a fund every month." },

  // People and rules
  { term: "SEBI", full: "Securities and Exchange Board of India", group: "People and rules", plain: "The regulator for stock markets and investment advice." },
  { term: "RIA", full: "SEBI Registered Investment Adviser", group: "People and rules", plain: "A person or firm registered with SEBI to give personal investment advice for a fee." },
  { term: "MFD", full: "Mutual Fund Distributor", group: "People and rules", plain: "Someone who sells mutual funds for commission. They may not give personal advice." },
  { term: "AMFI", full: "Association of Mutual Funds in India", group: "People and rules", plain: "The mutual fund industry body. It publishes daily fund prices and registers distributors." },
  { term: "ARN", full: "AMFI Registration Number", group: "People and rules", plain: "The registration number a mutual fund distributor needs." },
  { term: "CA", full: "Chartered Accountant", group: "People and rules", plain: "A qualified accountant. Many CA firms also handle clients' tax and investment records." },
  { term: "PAN", full: "Permanent Account Number", group: "People and rules", plain: "The 10-character income tax ID of every taxpayer. It links all of a person's statements, so we never send it out." },

  // Data and connections
  { term: "CAS", full: "Consolidated Account Statement", group: "Data and connections", plain: "One PDF listing everything a person holds. CAMS and KFintech send it for mutual funds; NSDL and CDSL send it for shares." },
  { term: "RTA", full: "Registrar and Transfer Agent", group: "Data and connections", plain: "Companies such as CAMS and KFintech that keep mutual fund ownership records for fund houses." },
  { term: "API", full: "Application Programming Interface", group: "Data and connections", plain: "A way for one program to ask another for data, so nobody has to copy numbers by hand.", example: "AI CFO asks Dhan's API: what does this client hold right now?" },
  { term: "Live connection", group: "Data and connections", plain: "A read-only link to the client's broker account. The client signs in on the broker's own page and approves; we then fetch current holdings." },
  { term: "Access pass", full: "Access token", group: "Data and connections", plain: "A temporary key the broker gives after the client approves. Dhan's lasts 24 hours. AI CFO uses it once and throws it away." },
  { term: "Consent flow", group: "Data and connections", plain: "The 'sign in on the provider's page and approve' pattern, like 'Log in with Google'. The app never sees the client's password." },
  { term: "Read-only", group: "Data and connections", plain: "Can look but cannot change anything. AI CFO's code has no way to place, change or cancel orders." },
  { term: "Reconciliation", group: "Data and connections", plain: "Comparing the same holding from two sources. If they disagree, the adviser decides; nothing is merged silently.", example: "Dhan says 80 Infosys shares, the statement says 75." },
  { term: "Snapshot", group: "Data and connections", plain: "A dated, frozen picture of the whole portfolio. Every report says which snapshot it used." },
  { term: "Account Aggregator", group: "Data and connections", plain: "A licensed framework for sharing financial data with the person's consent. Needs a regulated firm as the receiver." },

  // Security and privacy
  { term: "Anonymisation", group: "Security and privacy", plain: "Removing who a person is (name, PAN, phone, email, address) while keeping the financial facts.", example: "Asha Verma becomes C-DBB10631." },
  { term: "Pseudonymous code", group: "Security and privacy", plain: "A code that always means the same person inside one firm's data, but cannot be turned back into a name without the firm's secret key." },
  { term: "Encryption", group: "Security and privacy", plain: "Scrambling data so only someone with the key can read it." },
  { term: "Two-step sign-in", full: "Two-factor authentication", group: "Security and privacy", plain: "Signing in needs your password and a 6-digit code from your phone." },
  { term: "DPDP Act", full: "Digital Personal Data Protection Act, 2023", group: "Security and privacy", plain: "India's privacy law: clear consent, use only for the stated purpose, and the right to withdraw and be erased." },
  { term: "Audit trail", group: "Security and privacy", plain: "A permanent record of who did what and when. Each entry is chained to the previous one, so tampering shows." },

  // AI
  { term: "AI agent", group: "Artificial intelligence", plain: "A program that uses an AI model to make a decision or write something, using tools we give it." },
  { term: "Multi-agent system", group: "Artificial intelligence", plain: "Several agents with separate jobs working in a fixed order, like a small team: analysts, a writer, a checker." },
  { term: "LLM", full: "Large Language Model", group: "Artificial intelligence", plain: "The AI model that reads and writes text. AI CFO works without one, and uses one when the firm connects it." },
  { term: "RAG", full: "Retrieval-Augmented Generation", group: "Artificial intelligence", plain: "Before answering, the system looks up the right passage in a library of rules and quotes it, so answers come with sources." },
  { term: "Citation", group: "Artificial intelligence", plain: "The numbered source behind a sentence, such as [1], linking to the rule it came from." },
  { term: "Verifier", group: "Artificial intelligence", plain: "A checker that rejects any AI sentence containing a number the calculations did not produce." },
  { term: "Classifier", group: "Artificial intelligence", plain: "A small machine-learning model that scores how advice-like a sentence sounds, so risky wording is caught." },
];

export const glossaryIndex: Record<string, GlossaryEntry> = Object.fromEntries(glossary.map((g) => [g.term.toLowerCase(), g]));
