**Persona.** Our primary user is a GC/CM project manager on a public school modernization. They price change proposals from subcontractor quotes, give notice, and send proposals to the architect and the owner's rep, who return them over fees, markups or missing backup. Their record is spread across Procore, email, minutes and spreadsheets. The subcontractor PM is our second user; the owner's rep, our main stakeholder, is the person every proposal must satisfy. All three are on our research site, named by role only.

**How feedback changed it since Demo 3.**

- Demo 3 checked one proposal against the contract. Reviewing it, the owner's rep liked the whole team "working off the same pages." Demo 4 is that shared record, sub to owner: visibility follows the contract chain, and each role signs in to its own Home.
- He named schedule as the next layer of value. Demo 4 checks delay against the latest schedule update (critical path only), prices a day from the contract rate, and runs review clocks from the contract.
- He liked the two-step check (confirm the numbers, then check), so it is now required before a proposal can be sent.
- A CM from a large GC raised data-sharing concerns. The AI runs on free local models with no cloud calls, and every AI step logs a receipt.
- He pointed us to public records. Demo 4 is evaluated on 173 real RFIs with their official answers, from 6 public agency projects.

**What it tests about the thesis.** Our thesis is that AI agents can take RFI drafting off the GC, if every answer is tied to the project documents and a person still decides. The agent searches a project's own documents, drafts an answer, and quotes what it relied on. Code checks each quote word for word and compares the draft with the agency's published answer. On the 55 RFIs all three models finished:

- Quotes that check out: gemma4:12b 90%, llama3.1:8b 86%, qwen3.5:9b 73%.
- Yes/no answers matching the official one: best 60% (llama3.1), against 73% for always answering "no."
- Handed to a person when the answer needed new information: 67% (gemma4, qwen3.5) against 33% (llama3.1).

This supports the drafting half: grounded drafts with checkable quotes run offline at no cost, and bad quotes are caught automatically. It challenges the deciding half: no model beat a one-word rule on yes/no, and the most confident model was wrong more. On the Maine garage, llama3.1 said bidders need not price temporary heat; the agency said heat is required. So the product shows AI output as a blue draft a person confirms. Limits: small subsets (15 yes/no, 9 new-information), bid-phase RFIs only, one prompt, and word overlap is a rough measure.
