# Literature Scan — What Works / What Doesn't (fraud detection, adversarial setting)

Sources: arXiv API sweep, 2026-08-25. Semantic Scholar rate-limited (429) — arXiv only.

## What WORKS (evidence)

| Finding | Paper | Impact on LiveFire |
|---|---|---|
| Heterogeneous, time-aware multi-relational GNN over customer/merchant/device/IP + focal loss for imbalance | TMR-GGNN (2026, arXiv:2606.18444) | Informs the FUTURE graph tier — descoped in the global pivot (audit 04/07); roadmap input, not shipped architecture |
| Vanilla GNN aggregation FAILS on camouflaged fraudsters (context/feature/relation inconsistency) — needs consistency scoring + relation attention | GraphConsis (SIGIR'20, arXiv:2005.00625) | **Design change #1**: GNN tier must use consistency-filtered attention, not vanilla GCN |
| RL-driven adaptive attacker (FRAUD-RLA, IEEE TDSC 2025, arXiv:2502.02290) bypasses fraud classifiers under a limited-knowledge threat model | FRAUD-RLA (2025) | Validates our red-team arena; also a comparison baseline for our attack generator |
| Static rules/models degrade under adversarial drift; automated rule/model management maintains performance | ARMS (KDD'20, arXiv:2002.06075); ADAPT (ICDM'21) | Validates SHAP-feedback co-evolution loop = principled drift response |
| LLM + GCN hybrid (LLM supplies semantic features, GCN does structure) hits 0.98 acc on e-commerce payments | Luo et al. (2025, arXiv 2509.09258) | Informed the memo-injection heuristic design; the full LLM-semantic-feature tier is descoped (future work) |
| RL-post-trained small LLMs on textual txn data beat engineered-feature baselines on F1 | Lin et al. (2026, arXiv:2601.05578) | Future option: fine-tune bulk tier |
| One-class adversarial nets work when fraud labels are scarce | OCAN (2018, arXiv:1803.01798) | Backup if labeled attack data thin |

## What DOESN'T WORK (evidence — avoid or position honestly)

1. **LLMs directly on raw tabular fraud data**: "still lag behind specialized classifiers" even with retrieval-augmented feature serialization (FinFRE-RAG, ACL 2026, arXiv:2512.13040). → Our LLM tier is text/semantic ONLY, never raw tabular. Ledger will report it as assistive, not primary.
2. **Vanilla GNN message passing** on fraud graphs (camouflage inconsistency, GraphConsis above).
3. **Static models / fixed human rules** under adaptive adversaries (ARMS, FRAUD-RLA) — the exact failure mode our arena demonstrates on purpose.
4. **Unsupervised anomaly detection as primary detector**: autoencoders beat PCA but remain high-FP vs supervised; one-class methods only win when labels are absent (we have labels — use them).

## Net positioning

No published work combines: LLM red-team attack generation + co-evolution + SHAP feedback + heterogeneous-ensemble blue team + honest Robustness Ledger. FRAUD-RLA is the closest (RL attacker, static defender). Our novelty claim is the closed loop; the individual tiers are all literature-backed.

## Design changes adopted
1. GNN tier: consistency-attention heterogeneous GNN (GraphConsis-style), not vanilla GCN.
2. LLM tier: semantic/text features only; positioned as assistive in all metrics.
3. **Descope reality (audit 11/S4):** the GNN tier and the LLM-semantic-feature tier were
   both DESCOPED in the global pivot. The shipped blue team is XGB + LR + deterministic
   rules + IsolationForest; red-side memo injection is a deterministic stand-in for the
   semantic tier. Rows above are literature-backed roadmap input — do not cite them as
   shipped architecture.

