# AI for Life Science — 6-Month Upskilling Plan

**Created:** 2026-06-24
**Owner:** Junjie Chen (Research Scientist II, Lucence Diagnostics · Singapore)
**Goal:** Be competitive for **AI-for-Life-Science** roles within 6 months — anchored on
**genomics / multi-omics ML**, with **immunogenomics (peptide–MHC / TCR)** as the personal
differentiator that leverages his PhD immunology + HLA-typing + TCR-T background.
**Related:** `2026-06-24_personal_website_progress.md` (the blog is the visibility channel).

---

## 1. Context & positioning

Junjie already works in applied AI for Life Science (WGS pipelines, ML for cancer classification,
multi-omics). The aim is **not** to become a generic ML engineer (loses to CS PhDs) but to own the
**translational lane**: a real biologist who is also a credible deep-learning practitioner. The
six months convert "applied scientist who does some ML" → "ML scientist who deeply understands the
biology and the assay."

**Moat:** deep biology + wet-lab fluency + immunology/HLA/TCR + already doing genomics ML.
**Gaps to close:** (1) deep learning / PyTorch, (2) software-engineering rigor, (3) modern bio-ML
methods, (4) cloud + scalable pipelines, (5) public visibility.

## 2. Five skill pillars

1. **Deep learning (PyTorch)** — MLP → CNN → transformers → representation/embedding learning.
2. **Software & reproducibility** — git/GitHub, `pytest`, clean packaging, Docker, Nextflow/Snakemake, Weights & Biases.
3. **Modern bio-ML methods** — scverse (scanpy/scvi-tools), genomic/protein language models (Nucleotide Transformer, ESM-2), foundation models (scGPT, Geneformer), variant effect prediction, fragmentomics DL.
4. **Cloud + scale** — one cloud (GCP/AWS), GPU training (Colab/Lightning/Modal first).
5. **LLMs for science (stretch)** — embeddings + RAG over literature/ClinVar.

## 3. Six-month roadmap (overview)

| Phase | Focus | Output |
|---|---|---|
| **M1–2 Foundations** | PyTorch fluency + SWE habits (detailed schedule in §5) | Clean GitHub; "Project 0" containerized classifier; 2 blog posts; used a pretrained bio foundation model on cloud GPU |
| **M3–4 Bio-ML depth + Project 1** | scverse + HF bio models; build Project 1 reproducibly (W&B + Nextflow/Snakemake) | Project 1 repo + blog series; demoable pipeline |
| **M5–6 Differentiator + visibility** | Build Project 2 (immunogenomics); one Kaggle/TDC comp; aim for a bioRxiv preprint; start applying/networking | 2–3 portfolio projects; 1 preprint or Kaggle medal; applications out |

**Biggest accelerator:** his current Lucence job — push for more ML scope and a methods
paper/preprint; treat work problems as the curriculum; public projects are public-data echoes.

## 4. Portfolio projects (Months 3–6, seeded in Month 2)

1. **cfDNA fragmentomics DL classifier** — cancer detection/classification from fragment features (public cfDNA data, e.g. DELFI/Cristiano 2019; TCGA for tissue). Emphasize calibration & batch effects (his clinical edge).
2. **Peptide–MHC / TCR binding predictor** (the differentiator) — ESM-2 embeddings on IEDB epitopes / VDJdb TCRs. Fuses immunology PhD + HLA/TCR-T + protein LMs.
3. **Multi-omics representation learning** — scVI / scGPT / Geneformer on a public multi-omic single-cell dataset (CELLxGENE, Tabula Sapiens).
4. *(Stretch)* RAG assistant over ClinVar + literature for variant interpretation.

---

## 5. Month 1–2 — Week-by-week PyTorch schedule

**Time budget:** ~8–10 focused hrs/week. Suggested split each week: **~3–4h structured course ·
~4–5h hands-on coding · ~1h reading/writing.** Cadence: 2 short theory sessions + 1 longer build
session + a Friday "commit & note" ritual (push code, jot what you learned).

**Working setup (do once, Week 1):** conda/`uv` env, a public GitHub repo `bioml-learning`,
VS Code + Jupyter, Weights & Biases account. Everything goes to GitHub with a real README.

> Courses referenced: **Andrew Ng Deep Learning Specialization** (C1–C5, bottom-up theory),
> **fast.ai Practical Deep Learning** (top-down), **Karpathy "Neural Networks: Zero to Hero"**
> (transformers), **Hugging Face course**. Reading: *The Illustrated Transformer*, d2l.ai.

### Month 1 — PyTorch core + engineering habits

**Week 1 — Tensors, autograd, the training loop**
- Learn: PyTorch tensors & autograd; fast.ai Lesson 1 (inspiration); Ng **C1** wk1–2 (logistic regression *as* a neural net).
- Build: implement linear + logistic regression in **pure PyTorch** (manual training loop) on the sklearn **Wisconsin Breast Cancer** dataset (clinically themed, small).
- Ship: repo scaffold + README; first commit.
- ✅ Done when: you can write a from-scratch train loop (forward → loss → `backward()` → `step()`) and explain autograd.

**Week 2 — MLPs with `nn.Module`**
- Learn: Ng **C1** wk3–4 (shallow → deep nets, backprop intuition); `nn.Module`, optimizers, loss functions, `DataLoader`.
- Build: an MLP classifier on a **gene-expression tabular set** (small TCGA subset or a GEO dataset). Proper train/val/test split.
- Concept focus: **AUROC/AUPRC, not just accuracy** (clinical framing); class imbalance.
- ✅ Done when: a clean `nn.Module` MLP trains with a real eval metric and a learning curve.

**Week 3 — Making nets work: regularization, optimization, tracking**
- Learn: Ng **C2** (bias/variance, dropout, L2, batch/layer norm, Adam, LR schedules, hyperparameters).
- Build: take the Week-2 MLP, tune systematically; add **Weights & Biases** logging + sweeps.
- Concept focus: **calibration** — add a reliability/calibration curve (your clinical differentiator).
- ✅ Done when: W&B dashboard compares runs; you can reason about over/underfitting from curves.

**Week 4 — Structure & SWE: "Project 0"**
- Learn: Ng **C3** (ML strategy, short); Pro Git essentials; `pytest` basics.
- Build: refactor the notebook into a **clean package** (`src/` layout, config/argparse), add **tests**, a **Dockerfile**, and a reproducible env. This becomes **Project 0** — a polished, containerized bio-classifier.
- Ship: **Blog post #1** walking through Project 0 (your blog `posts/` template).
- ✅ Month-1 milestone: confident PyTorch training loop · clean tested repo · W&B · Docker · a clinically-evaluated classifier with calibration.

### Month 2 — Representation learning → transformers → foundation models

**Week 5 — CNNs & transfer learning**
- Learn: fast.ai Lessons 1–3; Ng **C4** (selected — convolutions, transfer learning).
- Build: a **1D-CNN on DNA sequence** (predict a regulatory/label task from sequence) — the on-ramp to genomic DL. (Alt: transfer-learn a pretrained CNN on a small histopathology set like PatchCamelyon.)
- Concept focus: convolutions as **motif detectors** (ties directly to genomics).
- ✅ Done when: a CNN trains end-to-end and you can explain why conv filters suit sequence/image data.

**Week 6 — Sequences & embeddings**
- Learn: tokenization, embeddings, sequence modeling; intro to attention.
- Build: use a **pretrained genomic/protein model as a feature extractor** — pull **ESM-2** (proteins) or **Nucleotide Transformer** (DNA) embeddings from Hugging Face and train a classifier head.
- Concept focus: **representation learning / transfer learning** — the core idea behind foundation models; bridges to your differentiator.
- ✅ Done when: you've turned raw bio-sequences into embeddings and beaten a naive baseline with them.

**Week 7 — Transformers & foundation models (the keystone week)**
- Learn: **Karpathy "Let's build GPT"** (Zero-to-Hero); *The Illustrated Transformer*; HF course ch.1–3 (attention, fine-tuning).
- Build: **fine-tune a small pretrained transformer** OR fine-tune an ESM-2 head for a protein/peptide task — run it on **cloud GPU** (Colab/Lightning/Modal): your first cloud-GPU training.
- Concept focus: self-attention; why foundation models transfer.
- ✅ Done when: you've fine-tuned a transformer on GPU and can sketch the attention mechanism.

**Week 8 — Capstone bridge + consolidation**
- Build: a small **end-to-end DL project on real bio data** previewing **Project 1 (cfDNA fragmentomics)** or **Project 2 (peptide–MHC)** — pretrained embedding + classifier, proper eval + calibration, W&B, containerized.
- Ship: **Blog post #2**; tidy the GitHub profile; write a short "Month 3–4 plan" note. Optionally enter a **Kaggle bio competition** for ongoing reps.
- ✅ Month-2 milestone: understands CNNs + transformers · has used a foundation model (ESM-2 / Nucleotide Transformer) on cloud GPU · 2nd portfolio project + 2 blog posts · ready to start Project 1/2.

### Progress checklist (tick as you go)
- [ ] W1 from-scratch PyTorch train loop (logistic regression)
- [ ] W2 MLP on gene-expression data with AUROC
- [ ] W3 W&B tracking + calibration curve
- [ ] W4 Project 0: tested, Dockerized package + **Blog post #1**
- [ ] W5 1D-CNN on DNA sequence
- [ ] W6 ESM-2 / Nucleotide Transformer embeddings + classifier
- [ ] W7 Fine-tuned transformer on **cloud GPU**
- [ ] W8 Capstone bridge project + **Blog post #2**

---

## 6. Resources (kept deliberately small)

- **DL:** fast.ai Practical Deep Learning · Andrew Ng DL Specialization (C1–C5) · d2l.ai · Karpathy "Neural Networks: Zero to Hero"
- **Transformers/LLMs:** The Illustrated Transformer · Hugging Face course
- **Bio-ML:** sc-best-practices.org · scverse (scanpy, scvi-tools) · Hugging Face (ESM-2, Nucleotide Transformer, scGPT/Geneformer) · DeepChem + Therapeutics Data Commons (tdcommons.ai)
- **Stats:** Intro to Statistical Learning (ISL)
- **Engineering:** Pro Git · `pytest` · Docker · Nextflow **or** Snakemake · Weights & Biases
- **Datasets:** sklearn Breast Cancer · TCGA/GTEx · PatchCamelyon · IEDB · VDJdb · CELLxGENE/Tabula Sapiens · Kaggle (Open Problems single-cell)
- **Singapore network:** A*STAR GIS / Bioinformatics Institute · NUS & Duke-NUS computational biology · local ML-in-bio meetups

## 7. Success metrics at month 6

- Clean **GitHub** with 2–3 documented bio-ML projects + a **blog** with real cadence.
- Fluent **PyTorch**; trained a transformer/embedding model end-to-end; can discuss architectures, evaluation, **and calibration/robustness**.
- One **reproducible pipeline** (Docker + Nextflow/Snakemake) + one cloud-GPU run.
- One **public credibility artifact**: bioRxiv preprint, Kaggle medal, or well-received tool/blog.
- Can hold an ML-scientist interview while being the only candidate who deeply understands the wet lab.

## 8. Notes / to revisit
- Confirm preferred branch if it shifts (genomics ML vs drug discovery vs foundation-model research) — re-weight projects accordingly.
- Re-evaluate at end of Month 2: if PyTorch feels solid earlier, pull Project 1 forward.
