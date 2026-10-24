# Historique des recherches Forest

173 essais enregistrés ; ordre d’enregistrement dans le journal, pas nécessairement ordre de fin entre arbres parallèles.

Les temps « objectif » sont ceux des évaluations natives : moyenne des répétitions de l’objectif, parfois une moyenne géométrique de plusieurs tailles/nombres de cœurs. Ils ne remplacent pas les temps par entrée de la comparaison finale. Les hypothèses et transformations ci-dessous sont les déclarations du générateur, conservées comme données expérimentales.

Moteur gelé hpc-forest-r1 ; méthode H, AB-MCTS-A, Mother persistante, memory-guided-v1, gpt-6-luna/max, graine 23, cible 1800 s, finish-started.

## aobench — job 781191

Campagne `aobench`. Pipeline achevé : **True**. Essais : 4. Commit retenu : `55803576af51607645a2efb3f3c2aea1a9ba8376`. Commit G : `55803576af51607645a2efb3f3c2aea1a9ba8376`. G confirmé : True.

Objectif naïf de recherche : 3,477879125 s ; retenu : 3,264254390 s ; G : 3,264254390 s.

Début UTC : 2026-10-23T18:02:43.387791+00:00 ; durée murale : 3753,4 s ; dépassement cible déclaré : 1953,4 s.

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | e8c86001631942e4 | infrastructure_error | NR | — |
| 2 | T2 | 9713eda73aa945e7 | valid | 3,267602322 | 714f7172c30622b71ad1cc9c24564bf560d9f394 |
| 3 | T3 | 513c6fff23d349bf | valid | 3,516215851 | ad191db455a1a67190cd7d33309a9d4101bbb20b |
| 4 | G | 0d48d5e87b2e40cd | valid | 3,265307742 | 55803576af51607645a2efb3f3c2aea1a9ba8376 |

### Essai 1 · T1 · e8c86001631942e4

Parent : `a2783dd4e776ed99ddf3564ad7560fd7856bd6df`. Statut mesuré : **infrastructure_error**.

Hypothèse déclarée : A static OpenMP scanline loop should reduce the dominant rendering cost on larger images while keeping scheduling overhead low. Seeding an independent PCG32 stream per pixel from the input seed removes shared mutable RNG state and makes results deterministic across threads and repeated calls. Small workloads may see parallel overhead; the controller must measure the candidate on official cases.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Parallelize disjoint scanlines with OpenMP static scheduling and the requested thread count, retaining a serial path for one thread or non-OpenMP builds.",
    "Replace shared drand48 state with deterministic, per-pixel PCG32 streams keyed by the input seed and pixel index; map output to uniform [0,1) samples.",
    "Preserve the primary sample loops, 64 ambient rays per hit, ray shading and pixel accumulation; clear the complete output before rendering."
  ]
}
```

Diagnostic : Codex attempted a tool call outside the authorized MCP access

### Essai 2 · T2 · 9713eda73aa945e7

Parent : `a2783dd4e776ed99ddf3564ad7560fd7856bd6df`. Statut mesuré : **valid**.

Hypothèse déclarée : Ambient rays from a given primary hit share the same origin. Computing each sphere's origin-to-center vector and quadratic constant, plus the plane's ray-origin numerator, once per AO call should reduce repeated scalar work in each of the 64 intersection tests without changing the tested geometry or hit-selection semantics.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Precompute each sphere's ray-origin offset vector and quadratic C term once per ambient-occlusion call, then use them for each ambient direction.",
    "Precompute the plane numerator for the common ambient-ray origin and reuse it while retaining the direction-dependent denominator and original parallel-ray threshold.",
    "Replace the ambient sphere loop with three explicit cached intersection calls in the same order, followed by the plane test; leave primary intersection and image dataflow unchanged."
  ]
}
```

### Essai 3 · T3 · 513c6fff23d349bf

Parent : `a2783dd4e776ed99ddf3564ad7560fd7856bd6df`. Statut mesuré : **valid**.

Hypothèse déclarée : Each primary sample currently rebuilds the same pixel ray origin and accumulates the same visibility into three separate channels. Hoisting the constant origin per pixel, accumulating visibility once in the unchanged sample order, and normalizing/writing that scalar to RGB once should reduce redundant per-sample and per-pixel work without changing ray directions, shading, or dimensions. Since run zero-initializes the output and all three channels receive the same ret sequence, the resulting channels should match; performance remains to be measured.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Hoisted the constant primary-ray origin assignment to once per pixel; each sample still overwrites all direction components and follows the same order.",
    "Accumulated each sample's AO visibility in one scalar, normalized once using a per-pixel sample-count invariant, and wrote the resulting value to each of the three output channels."
  ]
}
```

### Essai 4 · G · 0d48d5e87b2e40cd

Parent : `714f7172c30622b71ad1cc9c24564bf560d9f394`. Statut mesuré : **valid**.

Hypothèse déclarée : Combining T2's cached ambient-ray intersection terms with T3's single-accumulator primary pixel path may retain T2's measured benefit. T3 was slower alone, so only controller measurement of the combined program can establish whether the interaction is beneficial.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Kept T2's cached sphere origin offsets and quadratic terms, cached plane numerator, and explicit intersection calls in their original order.",
    "Applied T3's primary-ray origin hoist, single scalar visibility accumulator, and final replicated RGB writes while preserving primary sample order and counts."
  ]
}
```

## argmin — job 781166

Campagne `argmin`. Pipeline achevé : **True**. Essais : 8. Commit retenu : `638e4486d8c08c3315b7ec012a527697ad15741f`. Commit G : `638e4486d8c08c3315b7ec012a527697ad15741f`. G confirmé : True.

Objectif naïf de recherche : 0,000004457 s ; retenu : 0,000000393 s ; G : 0,000000393 s.

Début UTC : 2026-10-23T17:14:49.067130+00:00 ; durée murale : 2016,2 s ; dépassement cible déclaré : 216,2 s.

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | d885ce612026444c | valid | 0,000001836 | 31663c0f0f1a7c534cc061009fa8bbd0df254e46 |
| 2 | T2 | f5caf891d3ce4127 | valid | 0,000002803 | 994ae754b2a9dd12d8eb9a01ca4a39abd02f36ed |
| 3 | T1 | 293a28144f004842 | valid | 0,000001115 | 7b9e6ad6e54a8be17444f291cb908329ebf061ea |
| 4 | T2 | e6e6a3816d0a4a91 | valid | 0,000003072 | 470a2d7516d665ec579863b10fdfd70282433c6f |
| 5 | T1 | 0c88fcdc9709469c | valid | 0,000000575 | 3f4938376aafe72d04414d19fdcff93fb005753f |
| 6 | T2 | 807fbae617634b5e | valid | 0,000002555 | f4816a3654aab28a84fdc915376668b0865e3ff7 |
| 7 | T2 | 5f42ef130e824064 | valid | 0,000003645 | 1945d4566bd6237678aa12df6b6f00a330346ca4 |
| 8 | G | fb96f52a69f14e5e | valid | 0,000000366 | 638e4486d8c08c3315b7ec012a527697ad15741f |

### Essai 1 · T1 · d885ce612026444c

Parent : `69e3a85b77e52fb9e29ad49e81a9f8c191cda289`. Statut mesuré : **valid**.

Hypothèse déclarée : An OpenMP SIMD minimum reduction may reduce the serial argmin loop's per-element dependency without requiring a specific ISA. A forward equality scan then restores first-index semantics, but its extra input reads may offset the first-pass gain, particularly when the minimum occurs late. This candidate tests that two-pass tradeoff against the supplied baseline; no speedup or target code generation is assumed.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Use an OpenMP SIMD min reduction over the signed int values, initialized from the first element.",
    "Recover the earliest index with a forward equality scan, preserving first-index ties and exact integer-extrema behavior.",
    "Keep execution single-threaded and write index 0 for nonpositive n, matching the baseline's no-read behavior."
  ]
}
```

### Essai 2 · T2 · f5caf891d3ce4127

Parent : `69e3a85b77e52fb9e29ad49e81a9f8c191cda289`. Statut mesuré : **valid**.

Hypothèse déclarée : Four interleaved scalar (minimum, index) accumulators may shorten the loop-carried argmin dependency by updating each chain once per four inputs. This first variant retains conditional updates to isolate the multi-accumulator effect; a later branchless variant can contrast update behavior. The final signed-value and lowest-index merge preserves first-occurrence ties.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Maintain four independent scalar minimum-value/index pairs over interleaved input positions.",
    "Use conditional strict-less updates so equal values retain the earlier index within each accumulator.",
    "Process remaining tail elements and merge accumulators by signed value, then lowest index."
  ]
}
```

### Essai 3 · T1 · 293a28144f004842

Parent : `69e3a85b77e52fb9e29ad49e81a9f8c191cda289`. Statut mesuré : **valid**.

Hypothèse déclarée : A single OpenMP SIMD min reduction over a 64-bit key encoding (signed value, index) can preserve first-index argmin while avoiding the second input scan used by the prior valid two-pass candidate. For n=8192 this removes a 32 KiB logical reread, but adds 64-bit reduction work; neither target vectorization nor a speedup is assumed. The prior two-pass candidate measured 1.83637 µs mean versus the 4.46028 µs baseline, but those aggregates do not isolate random and decreasing inputs or explain the difference.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replace the scalar argmin loop with an OpenMP SIMD minimum reduction over 64-bit keys encoding signed-value order in the high bits and index in the low bits.",
    "Use the encoded index to return the earliest minimum directly, avoiding a second input scan while preserving first-index ties.",
    "Write index zero and return for nonpositive n; retain single-threaded execution and avoid ISA-specific intrinsics."
  ]
}
```

### Essai 4 · T2 · e6e6a3816d0a4a91

Parent : `994ae754b2a9dd12d8eb9a01ca4a39abd02f36ed`. Statut mesuré : **valid**.

Hypothèse déclarée : The measured four-accumulator conditional parent was correct and averaged 2.8029 µs versus the valid baseline's 4.4603 µs. This contrasting standalone candidate keeps its scalar partition and uses boolean/ternary selections for hot-loop value/index updates. If branch control is costly, selects may help; if updates are sparse and predictable, they may instead add work. The compiler's lowering and controller measurements will decide. The final signed-value and lowest-index merge preserves first-occurrence ties.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replace conditional minimum/index updates with boolean-controlled ternary selections in the four interleaved scalar accumulators, the tail, and the small-n path.",
    "Retain signed comparisons and merge accumulator results by minimum value, then lowest index, preserving first-occurrence ties.",
    "Keep the standalone scalar structure and output-write behavior; do not introduce threading or input-specific specialization."
  ]
}
```

### Essai 5 · T1 · 0c88fcdc9709469c

Parent : `69e3a85b77e52fb9e29ad49e81a9f8c191cda289`. Statut mesuré : **valid**.

Hypothèse déclarée : Chunking the input allows a portable OpenMP SIMD reduction over 32-bit values, with an index-recovery scan only in chunks whose minimum beats the best value seen so far. This may reduce rereads on random inputs compared with a full second pass, but on decreasing input every chunk can set a new record and cause up to another 32 KiB of reads at n=8192; per-chunk reduction overhead may also outweigh any benefit. Compare measured results with the one-pass packed-key and full two-pass candidates without assuming a speedup.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replace the full-array minimum reduction and unconditional full-array index-recovery scan with fixed-size blocks.",
    "Apply an OpenMP SIMD minimum reduction to each block and scan that block for the first matching index only when its minimum is strictly lower than the current best.",
    "Preserve signed int comparison and earlier-index ties; retain the nonpositive-n output path and single-threaded execution."
  ]
}
```

### Essai 6 · T2 · 807fbae617634b5e

Parent : `69e3a85b77e52fb9e29ad49e81a9f8c191cda289`. Statut mesuré : **valid**.

Hypothèse déclarée : Four conditional accumulators were the fastest prior T2 candidate, while the branchless four-accumulator variant was slower. Eight interleaved conditional minimum/index chains test whether additional scalar instruction-level parallelism helps, or whether extra comparisons and register pressure outweigh it. Per-lane strict comparisons and a signed-value/lowest-index merge preserve first-index ties.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "For n >= 8, initialize eight independent signed minimum/index pairs from the first eight elements.",
    "Scan full groups of eight with interleaved conditional updates, retaining first occurrence within each accumulator.",
    "Merge accumulator minima by signed value and then lowest index, and scan any remaining tail while preserving first-index ties.",
    "Retain a scalar baseline loop for smaller n and write the output on every path."
  ]
}
```

### Essai 7 · T2 · 5f42ef130e824064

Parent : `470a2d7516d665ec579863b10fdfd70282433c6f`. Statut mesuré : **valid**.

Hypothèse déclarée : Eight independent scalar minimum/index pairs with ternary updates may expose more instruction-level parallelism while avoiding conditional updates, but four-way branchless updates were slower than four-way conditional updates. This tests whether update style interacts with accumulator count; additional compares and register pressure may instead erase any benefit. Ternary source does not guarantee branch-free machine code, so the controller's compiler and measurements determine the outcome.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "For n >= 8, initialize eight independent signed minimum/index pairs from the first eight elements.",
    "Scan groups of eight with boolean/ternary updates and fold any remaining elements into accumulator zero.",
    "Merge accumulator results by signed value and then lowest index; use a scalar ternary-update path for smaller n and write the output on all valid-size paths."
  ]
}
```

### Essai 8 · G · fb96f52a69f14e5e

Parent : `3f4938376aafe72d04414d19fdcff93fb005753f`. Statut mesuré : **valid**.

Hypothèse déclarée : Deferring index recovery until all block minima are known should avoid rescanning every block that temporarily sets a new record, particularly for decreasing inputs. Scanning only the final winning block may also reduce reads on random inputs, though the controller must measure this distinct variant against the selected source.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Retain the 512-element blockwise OpenMP SIMD minimum reduction.",
    "Track the block that first establishes each strict global-minimum improvement without immediately rescanning it.",
    "After all block minima are computed, scan only the final winning block once for the first matching index; return zero directly when the initial value remains the minimum."
  ]
}
```

## base64 — job 781167

Campagne `base64`. Pipeline achevé : **True**. Essais : 3. Commit retenu : `28657d0677be5dfe6a44b7fb09de8f4dc2d5230e`. Commit G : `5d028ec0c8c79bf5aac78b33c9dfb91de78bff2f`. G confirmé : True.

Objectif naïf de recherche : 0,000055232 s ; retenu : 0,000055232 s ; G : 0,000071529 s.

**Le moteur a conservé le naïf.**

Début UTC : 2026-10-23T17:14:48.430900+00:00 ; durée murale : 2407,6 s ; dépassement cible déclaré : 607,6 s.

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | 195c725747a242b1 | infrastructure_error | NR | — |
| 2 | T2 | 1a3fa0daa49e4d17 | infrastructure_error | NR | — |
| 3 | G | fa6848073e084626 | valid | 0,000071403 | 5d028ec0c8c79bf5aac78b33c9dfb91de78bff2f |

### Essai 1 · T1 · 195c725747a242b1

Parent : `28657d0677be5dfe6a44b7fb09de8f4dc2d5230e`. Statut mesuré : **infrastructure_error**.

Diagnostic : Codex attempted a tool call outside the authorized MCP access

### Essai 2 · T2 · 1a3fa0daa49e4d17

Parent : `28657d0677be5dfe6a44b7fb09de8f4dc2d5230e`. Statut mesuré : **infrastructure_error**.

Diagnostic : Codex attempted a tool call outside the authorized MCP access

### Essai 3 · G · fa6848073e084626

Parent : `28657d0677be5dfe6a44b7fb09de8f4dc2d5230e`. Statut mesuré : **valid**.

Hypothèse déclarée : The prior candidate passed short scalar-only lengths but failed at n=64, where an AVX2 block ran. Replacing vector packing with scalar quartet packing after SIMD character mapping tests whether the fault was in the packing stage; any speedup remains unmeasured.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Conserver le mapping des 32 caractères via AVX2 mais empaqueter chaque groupe de quatre sextets avec des opérations scalaires.",
    "Garder une queue scalaire pour le dernier quartet paddé et écrire uniquement les octets décodés.",
    "Initialiser le champ réservé et écrire le compte décodé en uint64_t."
  ]
}
```

## binomial — job 781168

Campagne `binomial`. Pipeline achevé : **True**. Essais : 9. Commit retenu : `5ed8a5d1214ccbad796bf4f4c47e60942c104d1d`. Commit G : `5ed8a5d1214ccbad796bf4f4c47e60942c104d1d`. G confirmé : True.

Objectif naïf de recherche : 0,390943781 s ; retenu : 0,010448064 s ; G : 0,010448064 s.

Début UTC : 2026-10-23T17:14:48.376477+00:00 ; durée murale : 1776,6 s ; dépassement cible déclaré : 0,0 s.

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | 6211e2868857451b | valid | 0,070713501 | a66f18c51f94290b95716be4f98a7445402e6a8b |
| 2 | T2 | ad9409ade4d84760 | valid | 0,299400450 | 5b77aa9973d437325bc6011ad72d719278450c65 |
| 3 | T3 | 3e881ffd760b4417 | valid | 0,203769908 | e40bddfc4a0ecc69ea7c3e7973df8f7d4f2c5b40 |
| 4 | T2 | a4dc1431d193455e | valid | 0,299696899 | 286cc4b2bedbcf02334b8379afda0addfd45a235 |
| 5 | T1 | 385468c62d5049b9 | valid | 0,072102873 | 801be109abe371bb9b2781f46200822a62c1c7f9 |
| 6 | T3 | 8adff6908da1491e | valid | 0,133565935 | e18c69b4c1d61727bb142763d60cdba552e3795b |
| 7 | T1 | 4b17607d30c8451b | valid | 0,072568662 | 1f28998d0e99a791a2c3e926875cc5ff5de56bd2 |
| 8 | T2 | 9fdeb1845bb346bd | valid | 0,308561393 | 893a29412d2bfcf491cdd84c0de4816c8feb974a |
| 9 | G | 2c281c4e3f1340c3 | valid | 0,010425168 | 5ed8a5d1214ccbad796bf4f4c47e60942c104d1d |

### Essai 1 · T1 · 6211e2868857451b

Parent : `68f3b7aad61d85f984acbba6e729e61c5f298d32`. Statut mesuré : **valid**.

Hypothèse déclarée : Parallelizing the independent input-element loop with a static schedule should improve throughput for larger counts while preserving each element's arithmetic and reduction order. A thread-local V array avoids scratch sharing; for small counts, OpenMP overhead may offset any benefit. No candidate performance result is available yet.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Parallelized independent input elements with OpenMP, using the requested thread budget capped by the number of elements.",
    "Used static scheduling for the uniform per-element workload.",
    "Moved the scratch array into the parallel region for per-thread storage; preserved the original per-element initialization and backward reduction order."
  ]
}
```

### Essai 2 · T2 · ad9409ade4d84760

Parent : `68f3b7aad61d85f984acbba6e729e61c5f298d32`. Statut mesuré : **valid**.

Hypothèse déclarée : Replacing the 64 independent terminal powf calls per input with one initial power and 63 multiplications by u squared should reduce terminal-power evaluation cost. The payoff count and exponent endpoints remain unchanged, while repeated-multiplication rounding may affect numerical error and must be assessed by the controller.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Initialize the terminal power with powf(u, -64), matching the original j=0 exponent.",
    "Generate all 64 payoffs using upow *= u*u between entries, retaining the final exponent 62 and avoiding an unused final multiplication.",
    "Leave the backward reduction and all other source logic unchanged."
  ]
}
```

### Essai 3 · T3 · 3e881ffd760b4417

Parent : `68f3b7aad61d85f984acbba6e729e61c5f298d32`. Statut mesuré : **valid**.

Hypothèse déclarée : The baseline performs 2016 active backward updates per input after generating 64 terminal payoffs. For the same 64 payoff values and 63 transitions, the root value is their binomial-weighted sum with weights C(63,j) Pu^j (1-Pu)^(63-j), discounted 63 times. Computing that sum should reduce the transition work to a linear pass. Repeated powers and binomial coefficients avoid dividing by Pu or 1-Pu, including when either probability is exactly zero. This is an unmeasured performance hypothesis; numerical tolerance and runtime remain for the controller to evaluate.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replace the triangular backward induction with the binomial weighted sum over its 64 unchanged terminal payoffs and 63 transitions.",
    "Generate powers iteratively and binomial coefficients with a recurrence that divides only by the nonzero integer coefficient index, avoiding division by either probability.",
    "Apply the same one-step discount factor 63 times in the collapsed expression."
  ]
}
```

### Essai 4 · T2 · a4dc1431d193455e

Parent : `5b77aa9973d437325bc6011ad72d719278450c65`. Statut mesuré : **valid**.

Hypothèse déclarée : The selected parent's single-seed recurrence was measured as correct and faster than baseline (0.2994 s vs. 0.3918 s), with maximum reported absolute error 0.0002117. This contrasting variant re-anchors every 16 payoffs, using four powf calls per input and at most 15 multiplications between anchors. It may reduce accumulated float-rounding drift while retaining most of the powf reduction; the controller must measure its numerical error and runtime.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replaced the single 64-payoff recurrence with four 16-payoff blocks, each initialized by powf at its exact block-start exponent.",
    "Generated the remaining payoffs in each block by multiplying by u squared, without an unused multiplication after the block's final payoff.",
    "Kept all 64 payoffs and endpoint exponents (-64 through 62); left the backward reduction and other source logic unchanged."
  ]
}
```

### Essai 5 · T1 · 385468c62d5049b9

Parent : `68f3b7aad61d85f984acbba6e729e61c5f298d32`. Statut mesuré : **valid**.

Hypothèse déclarée : The prior valid OpenMP candidate had a lower aggregate mean time than baseline, but the available measurements do not isolate small-n overhead. This variant tests whether requiring at least eight input elements per worker, and otherwise using a direct serial loop, avoids team-startup cost for small workloads while retaining static outer-loop parallelism for larger counts. Each element's payoff initialization and backward reduction statements and order are unchanged; performance remains to be measured.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Extracted the unchanged per-element binomial arithmetic into a static inline helper so serial and parallel paths use the same payoff initialization and backward reduction order.",
    "Passed the threads argument through to the binomial routine and capped the OpenMP team size at the positive input count, with a one-thread fallback for nonpositive thread budgets.",
    "Used a direct serial loop when there is only one worker or fewer than eight elements per worker; otherwise used a static OpenMP work-sharing loop with a separate scratch array per worker."
  ]
}
```

### Essai 6 · T3 · 8adff6908da1491e

Parent : `68f3b7aad61d85f984acbba6e729e61c5f298d32`. Statut mesuré : **valid**.

Hypothèse déclarée : The earlier collapsed-sum candidate was valid and measured at 0.20377 s versus the 0.39176 s baseline, but it stores coefficient and probability-power arrays and performs 63 discount divisions per input. This contrasting version generates the same 64 payoff weights in place from the more heavily weighted endpoint, branches safely at probability endpoints, and computes the 63-step discount by exponentiation by squaring. It may reduce scratch traffic and discount divisions; the controller must measure both runtime and correctness.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replace the stored binomial coefficients and probability-power arrays with an endpoint-directed in-place recurrence over the same 64 terminal payoff values.",
    "Start the recurrence from pd^63 when pu <= pd and pu^63 otherwise, so the probability ratio denominator is nonzero at the pu=0 and pu=1 endpoints.",
    "Compute the equivalent 63-step discount factor with integer exponentiation by squaring instead of 63 successive divisions."
  ]
}
```

### Essai 7 · T1 · 4b17607d30c8451b

Parent : `68f3b7aad61d85f984acbba6e729e61c5f298d32`. Statut mesuré : **valid**.

Hypothèse déclarée : The catalog has two distinct valid programs: the static outer-loop candidate averaged 0.0707135 s, slightly faster than the eight-elements-per-worker cutoff variant at 0.0721029 s; both passed eight varied cases. Aggregate timings do not reveal per-size scaling. This contrasting implementation tests whether explicit balanced contiguous chunks reduce OpenMP work-sharing overhead, while keeping each element's arithmetic and reduction order unchanged. No speedup is assumed.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Extracted the unchanged per-element binomial calculation into a range helper, preserving terminal payoff initialization and backward reduction order; the serial routine uses the same helper.",
    "Added an OpenMP parallel path whose requested team size is capped by the positive input count and uses one worker for nonpositive thread budgets; it falls back to the serial routine when only one worker is requested.",
    "Manually divided the input into balanced contiguous ranges using the actual OpenMP team size, with each worker's range call owning its scratch array. Returned immediately for nonpositive counts."
  ]
}
```

### Essai 8 · T2 · 9fdeb1845bb346bd

Parent : `68f3b7aad61d85f984acbba6e729e61c5f298d32`. Statut mesuré : **valid**.

Hypothèse déclarée : The measured single-seed recurrence and 16-payoff re-anchored recurrence were both correct and had similar mean times (0.299400 s and 0.299697 s), while the 16-payoff version had lower maximum reported absolute error (5.25e-5 versus 2.12e-4). Re-anchoring every 8 payoffs tests whether more frequent powf anchors further reduce recurrence drift; it uses eight initial powers and 56 intervening multiplications per input. Runtime and numerical accuracy remain for the controller to measure.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replaced per-payoff powf evaluation with blocks of up to eight payoffs, initializing each block at its exact starting exponent using powf.",
    "Generated subsequent payoffs within each block by multiplying by u squared, stopping after the block's last payoff; all 64 payoffs and the -64 through 62 exponent range are retained.",
    "Left the backward reduction and all other source logic unchanged."
  ]
}
```

### Essai 9 · G · 2c281c4e3f1340c3

Parent : `a66f18c51f94290b95716be4f98a7445402e6a8b`. Statut mesuré : **valid**.

Hypothèse déclarée : Combining the measured outer-loop OpenMP path with recurrence-based terminal payoffs and the equivalent weighted terminal sum should reduce per-element work while respecting the requested thread budget. The standalone timings do not predict combined performance, and combined numerical error still requires validation.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Kept the selected OpenMP outer loop with a static schedule, a worker count capped by the input count, and per-worker scratch storage.",
    "Generated the 64 terminal payoff values from one powf(u, -64) seed using the u-squared recurrence, preserving the final exponent 62.",
    "Replaced the triangular fold with the endpoint-directed binomial-weighted sum over 64 payoffs and 63 transitions, accumulating in double and applying the 63-step discount factor."
  ]
}
```

## blackscholes — job 781169

Campagne `blackscholes`. Pipeline achevé : **True**. Essais : 7. Commit retenu : `043d577e5ff2678bf02c0c7111340a8cbbd096b4`. Commit G : `c9c4ff6a62f21474936e832eec812b7bca2c7c69`. G confirmé : True.

Objectif naïf de recherche : 0,007560900 s ; retenu : 0,001409835 s ; G : 0,001433297 s.

Début UTC : 2026-10-23T17:14:50.728743+00:00 ; durée murale : 1890,0 s ; dépassement cible déclaré : 90,0 s.

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | 803094c58b8b4d6c | valid | 0,001421678 | e4ee44a3a8215e4b023484c6f3a4dbbf4f0039be |
| 2 | T2 | a796f24ac8104fbd | generation_failed | NR | — |
| 3 | T1 | 8f6218f1ecd7468b | valid | 0,001411702 | 043d577e5ff2678bf02c0c7111340a8cbbd096b4 |
| 4 | T1 | 6409874e90b44c9e | valid | 0,001413384 | 78b67fe4826f3fc61c4ab2be15034c43091218c2 |
| 5 | T1 | a6dcf4b8b5c14a50 | valid | 0,001411305 | 3407d8573d94a4b75d04b38112b1d4563179bc1d |
| 6 | T1 | e391956882f748c9 | valid | 0,004815010 | acd6bb16d03bf099b0dde79869c0d8e62d77a9ce |
| 7 | G | 3da70667130345fd | valid | 0,001436345 | c9c4ff6a62f21474936e832eec812b7bca2c7c69 |

### Essai 1 · T1 · 803094c58b8b4d6c

Parent : `779e7230028fac71272afa7059be4da0f2258f9b`. Statut mesuré : **valid**.

Hypothèse déclarée : Each option requires independent scalar transcendental calculations, so a contiguous static OpenMP workshare can use the supplied CPU budget for large arrays while preserving the original per-element computation. A generic serial path below 256 elements should avoid parallel startup overhead on small arrays. The results need measurement across thread budgets and sizes; no speedup is assumed.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Factored the unchanged scalar Black-Scholes calculation into a per-index helper used by the serial kernel and parallel loop.",
    "Added an OpenMP parallel-for with contiguous static scheduling, explicitly capped to min(threads, count).",
    "Kept a serial path for counts below 256 or a requested thread budget of one or less, and passed the supplied thread budget from run()."
  ]
}
```

### Essai 2 · T2 · a796f24ac8104fbd

Parent : `779e7230028fac71272afa7059be4da0f2258f9b`. Statut mesuré : **generation_failed**.

Hypothèse déclarée : The scalar baseline already reuses sqrtf(T) and evaluates the CND polynomial in Horner form. Adding only an OpenMP SIMD annotation may let GCC lower independent per-element math more efficiently without parallel-scheduling overhead. The candidate makes no ISA, vector-math ABI, approximation, or external-library assumption; any benefit and numerical effects require controller measurement.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Add #pragma omp simd to the independent Black-Scholes per-element loop; leave scalar arithmetic, thread policy, and output writes unchanged."
  ]
}
```

Diagnostic : Documentation action ended without a subsequent source proposal

### Essai 3 · T1 · 8f6218f1ecd7468b

Parent : `779e7230028fac71272afa7059be4da0f2258f9b`. Statut mesuré : **valid**.

Hypothèse déclarée : The prior T1 candidate added contiguous schedule(static) worksharing with a serial path below 256 elements; it was correct on all 8 supplied cases and measured 0.0014217 seconds versus the baseline's 0.0075171 seconds, but the catalog contains only one distinct T1 program and no thread-budget scaling comparison. This candidate keeps the scalar formula, threshold, and worker cap, while using static chunks sized for about four chunks per worker. It tests whether modest static chunking helps balance input-dependent cost variation, while risking locality loss versus contiguous static scheduling. No speedup is assumed; compare both candidates on the same sizes and thread budgets.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Kept the original serial Black-Scholes loop as the control path and left the binomial kernel unchanged.",
    "Added a parallel loop with the same scalar per-element formula, an explicit worker cap of min(threads, count), and a static chunk size targeting about four chunks per worker.",
    "Retained a serial path for counts below 256 or thread budgets of one or less; every element in the selected path writes its corresponding output."
  ]
}
```

### Essai 4 · T1 · 6409874e90b44c9e

Parent : `779e7230028fac71272afa7059be4da0f2258f9b`. Statut mesuré : **valid**.

Hypothèse déclarée : The two prior correct static-schedule candidates have close aggregate means (0.0014117 s and 0.0014217 s), but the available results do not resolve scheduling or scaling by size and thread budget. This candidate keeps the scalar formula and 256-element serial path, while testing dynamic scheduling with roughly four chunks per worker. Dynamic assignment may balance input-dependent per-element cost; scheduling overhead and weaker locality may instead make it slower. The explicit worker cap is min(threads, count), so the requested CPU budget is not exceeded.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Kept the original black_scholes_serial kernel unchanged as the small-work and single-thread path.",
    "Added a parallel loop that preserves the scalar per-element formula and uses dynamic chunks sized to target about four chunks per worker, with a minimum chunk size of one.",
    "Dispatches to the serial kernel for n < 256 or threads <= 1; otherwise caps the OpenMP team at min(threads, n). Each loop iteration writes its corresponding output element."
  ]
}
```

### Essai 5 · T1 · a6dcf4b8b5c14a50

Parent : `779e7230028fac71272afa7059be4da0f2258f9b`. Statut mesuré : **valid**.

Hypothèse déclarée : The prior parallel candidates are all correct on the supplied cases, but their aggregate means are close and do not establish schedule or thread-budget scaling. Keeping the scalar calculation and the 256-element serial cutoff fixed while using OpenMP guided scheduling with a minimum chunk of one tests whether larger early chunks and progressively finer assignment balance work with less dispatch overhead than dynamic scheduling. Guided scheduling may still lose to contiguous static work through scheduler cost or locality effects; no speedup is assumed.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Kept black_scholes_serial unchanged as the small-work and single-thread control path.",
    "Added a guided OpenMP workshare for counts of at least 256, with a minimum chunk size of one and a team capped at min(threads, count).",
    "Preserved the scalar per-element computation and writes one result per parallel loop iteration.",
    "Left the binomial kernel unchanged."
  ]
}
```

### Essai 6 · T1 · e391956882f748c9

Parent : `3407d8573d94a4b75d04b38112b1d4563179bc1d`. Statut mesuré : **valid**.

Hypothèse déclarée : Replacing guided scheduling with schedule(static,1) tests whether cyclic assignment's finer interleaving helps if per-element costs vary. The scalar calculation, 256-element serial cutoff, and worker cap remain fixed. Since each iteration performs similar transcendental work, cyclic assignment may instead lose to the prior schedules through poorer locality; no speedup is assumed.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Changed the parallel loop from guided scheduling to cyclic static scheduling with chunk size one; kept the per-element scalar calculation unchanged.",
    "Retained the serial path below 256 elements or for a thread budget of one or less, and capped requested workers at min(threads, count).",
    "Renamed the parallel kernel to reflect its schedule and updated run() to call it; left the binomial kernel unchanged."
  ]
}
```

### Essai 7 · G · 3da70667130345fd

Parent : `3407d8573d94a4b75d04b38112b1d4563179bc1d`. Statut mesuré : **valid**.

Hypothèse déclarée : The per-element kernel has broadly uniform work, so contiguous static assignment may reduce dispatch overhead and improve locality versus guided scheduling. The slower measured static,1 result tested cyclic tiny chunks, not default contiguous static scheduling. This candidate changes only that schedule choice while retaining the selected parallel kernel's thread cap, serial cutoff, and FP32 calculation; its correctness and performance remain unmeasured.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Changed the OpenMP loop schedule from guided,1 to default contiguous static scheduling; preserved the scalar kernel, serial cutoff, and worker cap."
  ]
}
```

## deferred — job 781194

Campagne `deferred`. Pipeline achevé : **False**. Essais : 0. Commit retenu : `aucun`. Commit G : `aucun`. G confirmé : False.

Objectif naïf de recherche : NR s ; retenu : NR s ; G : NR s.

Erreur de pipeline : InfrastructureError: Mother did not produce a valid research forest: not_invoked_source_limit

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|

## deferred — job 781198

Campagne `deferred_r2`. Pipeline achevé : **True**. Essais : 6. Commit retenu : `5820ee9ced976b03b4f2a20f32ec3df7f962e60f`. Commit G : `5820ee9ced976b03b4f2a20f32ec3df7f962e60f`. G confirmé : True.

Objectif naïf de recherche : 0,115005712 s ; retenu : 0,061736630 s ; G : 0,061736630 s.

Début UTC : 2026-10-23T18:14:06.908323+00:00 ; durée murale : 1491,5 s ; dépassement cible déclaré : 0,0 s.

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | d8ef833859734137 | infrastructure_error | NR | — |
| 2 | T2 | f5977ba004e2449f | infrastructure_error | NR | — |
| 3 | T3 | 8a297350773846ea | infrastructure_error | NR | — |
| 4 | G | f1425ec287b64103 | valid | 0,062784050 | b7a0340854a5adf1afd153f0b11f1c8adffdf7a3 |
| 5 | G | b1d609dedded470c | valid | 0,062416690 | 34fb41d5db0c01ec1a03251f41e8b9ff2885dabb |
| 6 | G | 5b59d34900644eb0 | valid | 0,061926420 | 5820ee9ced976b03b4f2a20f32ec3df7f962e60f |

### Essai 1 · T1 · d8ef833859734137

Parent : `498ce5a9bf8612e3712ae5663b2dee60313406b4`. Statut mesuré : **infrastructure_error**.

Diagnostic : Codex attempted a tool call outside the authorized MCP access

### Essai 2 · T2 · f5977ba004e2449f

Parent : `498ce5a9bf8612e3712ae5663b2dee60313406b4`. Statut mesuré : **infrastructure_error**.

Diagnostic : Codex attempted a tool call outside the authorized MCP access

### Essai 3 · T3 · 8a297350773846ea

Parent : `498ce5a9bf8612e3712ae5663b2dee60313406b4`. Statut mesuré : **infrastructure_error**.

Diagnostic : Codex attempted a tool call outside the authorized MCP access

### Essai 4 · G · f1425ec287b64103

Parent : `498ce5a9bf8612e3712ae5663b2dee60313406b4`. Statut mesuré : **valid**.

Hypothèse déclarée : Parallelizing independent root-tile shading should use multiple cores while preserving serial output and the per-call depth update. A dynamic one-tile schedule may help balance uneven root workloads; this remains unmeasured.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Pass the `threads` budget to `DispatchDynamicC` and parallelize its independent root-tile shading loop with OpenMP dynamic scheduling, bounded to the number of root tiles; retain a direct serial loop for one-thread or non-OpenMP execution."
  ]
}
```

### Essai 5 · G · b1d609dedded470c

Parent : `b7a0340854a5adf1afd153f0b11f1c8adffdf7a3`. Statut mesuré : **valid**.

Hypothèse déclarée : Parallelizing the current-frame depth bounds should complement the measured root-tile speedup by reducing the remaining serial preprocessing, while preserving the z-bound values through independent writes and level barriers.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Parallelize current-frame base depth-bounds scans across tile rows, bounded by `threads`, with disjoint output ranges.",
    "Parallelize independent depth-tree reduction nodes at each level and rely on the worksharing barrier before building the next level.",
    "Retain f1425's thread-bounded dynamic root-tile shading loop."
  ]
}
```

### Essai 6 · G · 5b59d34900644eb0

Parent : `34fb41d5db0c01ec1a03251f41e8b9ff2885dabb`. Statut mesuré : **valid**.

Hypothèse déclarée : Precomputing reciprocal camera-projection terms once per shaded tile may remove repeated per-pixel divisions, with only rounding-level changes in reconstructed positions. Whether it improves end-to-end time is unmeasured and requires controller validation.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Retain the thread-budgeted OpenMP dynamic root-tile shading loop from the selected base.",
    "Retain parallel current-frame base depth scans and per-level reductions with synchronization between levels.",
    "Hoist reciprocal camera projection coefficients outside the per-pixel loops and use multiplication for view-position reconstruction; preserve BRDF and gamma calculations."
  ]
}
```

## gemm_cpu — job 781170

Campagne `gemm_cpu`. Pipeline achevé : **True**. Essais : 6. Commit retenu : `0ecb5936ff627da58938a56d56a8dec416f2c2b2`. Commit G : `cbe7a14fbdebb39504379334337f6fa487b061a2`. G confirmé : True.

Objectif naïf de recherche : 5,690184368 s ; retenu : 0,005796701 s ; G : 0,006501022 s.

Début UTC : 2026-10-23T17:14:50.877433+00:00 ; durée murale : 1856,0 s ; dépassement cible déclaré : 56,0 s.

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | c8e98769ea314eec | valid | 0,009861111 | 455b51d188ff7681d1eb2ccaffe0711bf017ef48 |
| 2 | T2 | 627c8feab8e44462 | valid | 0,019979412 | 20efda3c6255698fd0da6977c5daf77d893fa6c7 |
| 3 | T3 | 2257ee21dd9f48ef | valid | 0,008898867 | 0ecb5936ff627da58938a56d56a8dec416f2c2b2 |
| 4 | T2 | 43ad7178615f4c86 | valid | 0,035555279 | 0e0cc08c936a37055a47ea0cbbd403d5502c2335 |
| 5 | T1 | fe0ff35d35924642 | valid | 0,009827050 | 6bb8fa1c4c1b0bee8fe23af0217a9942ef67ea35 |
| 6 | G | f33fef2224cc4ca9 | valid | 0,009057974 | cbe7a14fbdebb39504379334337f6fa487b061a2 |

### Essai 1 · T1 · c8e98769ea314eec

Parent : `24af6b394ae97df68f4155379458edf65164e397`. Statut mesuré : **valid**.

Hypothèse déclarée : Changing the traversal to r-k-c makes each inner loop stream contiguous columns of B and C, which may improve memory access and permit compiler vectorization. Static ownership of distinct rows avoids output races while parallelizing initialization and computation across no more than the positive threads argument. The candidate has not yet been measured.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replaced fixed-size template dispatch with runtime-dimension indexing for generic square matrices.",
    "Changed the computation to r-k-c so the inner column loop traverses B and C contiguously.",
    "Assigned output rows with a static OpenMP parallel-for, clamped to at most the positive threads count and available rows; zeroed each row before accumulating."
  ]
}
```

### Essai 2 · T2 · 627c8feab8e44462

Parent : `24af6b394ae97df68f4155379458edf65164e397`. Statut mesuré : **valid**.

Hypothèse déclarée : Assigning each thread a disjoint 32x64 output tile and reducing through 64-wide K blocks should improve cache reuse: B rows are streamed contiguously, A scalars are reused across a tile's columns, and C remains local across K blocks. This is a performance hypothesis only; the controller must measure it.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replace the unblocked row-column-reduction kernel with 32x64 output tiles and 64-wide K blocks.",
    "Parallelize collapsed output-tile coordinates with static scheduling so each tile has exclusive ownership and is fully initialized before accumulation.",
    "Use i-k-j accumulation with contiguous B/C accesses and compiler-generated SIMD on the contiguous column loop; retain ascending K order and handle all tile fringes.",
    "Use no explicit x86 intrinsics or packed-panel transformations."
  ]
}
```

### Essai 3 · T3 · 2257ee21dd9f48ef

Parent : `24af6b394ae97df68f4155379458edf65164e397`. Statut mesuré : **valid**.

Hypothèse déclarée : A single 4x16 AVX2/FMA register microkernel should reduce scalar accumulation overhead while reusing each loaded B vector across four output rows and broadcasting each A value across sixteen output columns. Isolating AVX2/FMA in a GCC target-attributed function and checking CPU support at runtime avoids depending on unspecified global ISA flags; scalar handling covers incomplete tiles and unsupported CPUs. No speedup is assumed before official measurements.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replace scalar r-c-k accumulation on supported x86 CPUs with a 4x16 AVX2/FMA register kernel: eight output vectors are accumulated; B vectors are shared across four rows and each A scalar is broadcast across two vectors.",
    "Use a GCC per-function target(\"avx2,fma\") attribute and runtime AVX2/FMA detection, retaining a scalar fallback when the CPU lacks either feature.",
    "Handle incomplete column groups and remaining rows with scalar reductions; assign every output from a zero-initialized accumulator on each call rather than relying on prior output contents.",
    "Parallelize independent four-row blocks, or scalar fallback rows, with OpenMP limited by the supplied thread count."
  ]
}
```

### Essai 4 · T2 · 43ad7178615f4c86

Parent : `20efda3c6255698fd0da6977c5daf77d893fa6c7`. Statut mesuré : **valid**.

Hypothèse déclarée : The selected 32x64x64 tiled parent is correct and fast, but processes output tiles row-panel-major. Test a contrasting 16x128x32 shape and column-panel-major static scheduling: the 16x128 output tile has the same element count, while each K block touches 8 KiB of C, 16 KiB of B and 2 KiB of A. At n=1024, the collapsed loop order may also give each static worker a contiguous set of row tiles for one wider B panel, improving cache reuse. This is a performance hypothesis; the controller must measure it.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Change the output tile from 32x64 to 16x128 and the K block from 64 to 32, retaining the same output tile area.",
    "Swap the collapsed tile-loop order to process column panels outside row tiles with static scheduling, while keeping exclusive output-tile ownership.",
    "Initialize every output element in its tile before accumulation, retain ascending K traversal, handle all fringes, and use only compiler-generated SIMD on the contiguous column loop."
  ]
}
```

### Essai 5 · T1 · fe0ff35d35924642

Parent : `24af6b394ae97df68f4155379458edf65164e397`. Statut mesuré : **valid**.

Hypothèse déclarée : The measured r-k-c candidate (c8e98769ea314eec) is valid and much faster than baseline-e1, but the catalog has only one distinct program. This contrasting variant tests whether a separate contiguous parallel output-initialization pass, within the same OpenMP team, is better or worse than fusing initialization into each owned row; the compute pass retains static disjoint row ownership and a contiguous inner-column loop. This candidate has not been measured.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replaced the fixed-size template dispatch with generic runtime dimension indexing using size_t offsets.",
    "Clamped the worker count to the positive requested thread count and number of rows, with a one-worker fallback for nonpositive thread requests.",
    "Used one OpenMP team for a separate statically scheduled contiguous output-zeroing pass followed by a statically scheduled row-disjoint r-k-c computation pass.",
    "Kept the innermost column loop contiguous and avoided explicit intrinsics and cache-panel packing."
  ]
}
```

### Essai 6 · G · f33fef2224cc4ca9

Parent : `0ecb5936ff627da58938a56d56a8dec416f2c2b2`. Statut mesuré : **valid**.

Hypothèse déclarée : The valid AVX2/FMA 4x16 kernel is the fastest measured program so far. This experiment keeps that microkernel but schedules column tiles outside four-row blocks, so each worker processes rows for a narrower B panel before moving to the next panel. It tests whether improved cache residency outweighs the changed task ordering; no speedup is assumed.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Retained the source candidate's 4x16 AVX2/FMA register microkernel, CPU feature dispatch, and scalar handling for unsupported CPUs and incomplete tiles.",
    "Changed work assignment to statically schedule column tiles outside independent four-row blocks, testing reuse of a narrower B panel across row blocks.",
    "Clamped OpenMP threads to the positive request and the eight-thread ceiling."
  ]
}
```

## mandelbrot — job 781171

Campagne `mandelbrot`. Pipeline achevé : **True**. Essais : 5. Commit retenu : `6a17decffee591711d0406ef41be1641aa462bca`. Commit G : `6a17decffee591711d0406ef41be1641aa462bca`. G confirmé : True.

Objectif naïf de recherche : 0,563238906 s ; retenu : 0,282400629 s ; G : 0,282400629 s.

Début UTC : 2026-10-23T17:14:52.878916+00:00 ; durée murale : 1506,2 s ; dépassement cible déclaré : 0,0 s.

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | 617e43a343db41d9 | valid | 0,282563045 | 5d72d9b5189aa19c5c7350ba0deb118772572b95 |
| 2 | T2 | 3fdf829297bc4ab1 | valid | 0,746226072 | ae10d3750204b2ddef1df3492e63c575ff652251 |
| 3 | T3 | 6cf83051717c427a | valid | 0,563420985 | 1f26a582028511d14978a15362bee527d18f9345 |
| 4 | T3 | c8ce6ea6d4fb4d25 | valid | 0,564304739 | 4df88a810d995dada655c6da4542ad0eb512c4dd |
| 5 | G | 18b0d19cd66f4f4f | valid | 0,282356879 | 6a17decffee591711d0406ef41be1641aa462bca |

### Essai 1 · T1 · 617e43a343db41d9

Parent : `52442759da2e3c634d6058da587a7e736c56ce4e`. Statut mesuré : **valid**.

Hypothèse déclarée : At multiple threads, variable per-pixel iteration counts may leave contiguous row assignments imbalanced. Dispatching 64-by-4 pixel tiles dynamically (one tile per scheduling chunk) should improve balance while limiting scheduling overhead; the unchanged serial path avoids OpenMP setup at one thread. Whether this beats a contiguous static-row implementation remains to be measured.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Retained the baseline serial implementation as the low-overhead path when threads is at most one.",
    "For multiple threads, partitioned the image into 64-by-4 tiles and scheduled tile indices with OpenMP dynamic scheduling and chunk size one.",
    "Kept the baseline coordinate expressions, Mandelbrot recurrence, output indexing, and one-write-per-pixel behavior."
  ]
}
```

### Essai 2 · T2 · 3fdf829297bc4ab1

Parent : `52442759da2e3c634d6058da587a7e736c56ce4e`. Statut mesuré : **valid**.

Hypothèse déclarée : Processing adjacent pixels in four-lane batches with an explicit active mask may expose SIMD parallelism across independent recurrences. A reduction detects when every lane has escaped, while the scalar tail preserves behavior for widths not divisible by four. Divergence and mask overhead may offset the gains; the fixed compiler build must determine the usable instructions.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Batch adjacent pixels in groups of four and apply OpenMP SIMD to lane initialization, masked recurrence updates, and output writes.",
    "Track active lanes and use a reduction to terminate a batch once all lanes have escaped.",
    "Use the original scalar recurrence for the remaining vector tail."
  ]
}
```

### Essai 3 · T3 · 6cf83051717c427a

Parent : `52442759da2e3c634d6058da587a7e736c56ce4e`. Statut mesuré : **valid**.

Hypothèse déclarée : Explicitly storing the real and imaginary squares once per scalar iteration may avoid repeated multiplications between the escape test and recurrence update if the compiler does not already reuse them; GCC may already eliminate the redundancy, so any benefit must be measured.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Compute the real and imaginary squares once per iteration and reuse them in both the strict escape test and the real recurrence update."
  ]
}
```

### Essai 4 · T3 · c8ce6ea6d4fb4d25

Parent : `52442759da2e3c634d6058da587a7e736c56ce4e`. Statut mesuré : **valid**.

Hypothèse déclarée : The prior explicit-local-square trial was valid but produced the same binary SHA-256 as baseline, with only a very small timing difference. This contrasting loop-carried cache keeps each state's real and imaginary squares for both the strict escape check and real update; it tests whether this representation changes compiler scheduling or branch cost, while preserving the recurrence's float operation order and count behavior. It may compile identically or be slower due to the conditional cache refresh.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Carry the current real and imaginary squares across scalar recurrence iterations and reuse them for the strict escape comparison and real update; refresh only when another iteration remains. Keep coordinate generation, recurrence expression order, float temporaries, and iteration limits unchanged."
  ]
}
```

### Essai 5 · G · 18b0d19cd66f4f4f

Parent : `5d72d9b5189aa19c5c7350ba0deb118772572b95`. Statut mesuré : **valid**.

Hypothèse déclarée : Keeping the selected T1 dynamic tile scheduling and 256 pixels per full tile while changing the shape from 64x4 to 32x8 tests whether taller, narrower tiles affect load distribution or locality. At n=1024 the tile count remains 6144, isolating shape more closely; other valid sizes use the same general tiling logic. Performance is unmeasured, and the one-thread path is unchanged.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Retained T1's one-thread serial path and dynamic OpenMP scheduling of two-dimensional tiles using the supplied thread budget.",
    "Changed tile geometry from 64x4 to 32x8, preserving 256 pixels per full tile and the same 6144 tiles at n=1024.",
    "Preserved coordinate expressions, Mandelbrot recurrence, output indexing, and tail coverage for dimensions not divisible by tile dimensions."
  ]
}
```

## noise — job 781172

Campagne `noise`. Pipeline achevé : **True**. Essais : 11. Commit retenu : `5d7dc3713d9a28c3a1d90d7ea9c461ec7b605ccd`. Commit G : `5d7dc3713d9a28c3a1d90d7ea9c461ec7b605ccd`. G confirmé : True.

Objectif naïf de recherche : 0,311421502 s ; retenu : 0,262255191 s ; G : 0,262255191 s.

Début UTC : 2026-10-23T17:14:53.146686+00:00 ; durée murale : 1733,2 s ; dépassement cible déclaré : 0,0 s.

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | 1b563849b77d4fb6 | valid | 0,264444441 | 8a4c91500f9c1573eb8cfb4f71eb98a3c140ca09 |
| 2 | T2 | 3a73a2bc81a74440 | valid | 0,312179456 | b3e287dab815b11d4cc47ae2757b53710dd4cda3 |
| 3 | T3 | ef062539f7784946 | valid | 0,309183689 | f705a5068386ffceaad2e9f9b2928ce67370ba5f |
| 4 | T1 | c47661bf0c474573 | valid | 0,305759448 | fc055ab914e4f12b858f8c95ca1f459f719640cc |
| 5 | T2 | 4a9a5cce5660497f | valid | 0,306052326 | 76aa545f89d120a0547d25341ebe1dfd0ceddb76 |
| 6 | T3 | e4f7d4c328f24f12 | valid | 0,313531432 | f655cbb15ac6a69011bd990c7a87dd725184970f |
| 7 | T1 | 9f01e3ccd2534b37 | valid | 0,289608644 | 59b89c0b3e1d438ab3e4979010ffd9efc24ccd08 |
| 8 | T2 | c971305fc3a54f5b | valid | 0,308320735 | a0f6991ee22a1409776af5e1eb15c31521ea9599 |
| 9 | T3 | 15645d25f2d54ea6 | valid | 0,306682914 | d0d2e6fce935b3e7928bb51771ab8393267a81c2 |
| 10 | T1 | cdfe6a8a2f234171 | valid | 0,289577601 | 35fb7d91edac3f30c2d1f8b3189e49bf2f3ed1db |
| 11 | G | f8027a9605d642a5 | valid | 0,262176185 | 5d7dc3713d9a28c3a1d90d7ea9c461ec7b605ccd |

### Essai 1 · T1 · 1b563849b77d4fb6

Parent : `2af6b431524cfeeb7794f62f248cbda0b6b24ae0`. Statut mesuré : **valid**.

Hypothèse déclarée : Explicitly sharing the two first-level and four second-level permutation results should reduce redundant corner-hash loads and expose reuse, while retaining the same eight final lookups and all floating-point expressions. The baseline is correct at 0.312358913 s; compiler load coalescing has not been observed here, so this candidate should still be measured.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Factor the shared x permutation results once per Noise call and reuse them for four y-level results.",
    "Compute the eight final permutation hashes explicitly, then pass those hashes to Grad with the original corner offsets.",
    "Leave NoiseWeight, interpolation, output traversal, ABI, and full-output overwrite behavior unchanged."
  ]
}
```

### Essai 2 · T2 · 3a73a2bc81a74440

Parent : `2af6b431524cfeeb7794f62f248cbda0b6b24ae0`. Statut mesuré : **valid**.

Hypothèse déclarée : Replacing NoiseWeight's separately formed t^4 and weighted terms with t^3 * (t * (6t - 15) + 10) expresses the same fade polynomial in Horner form and may reduce scalar arithmetic. It changes only fade evaluation; because floating-point rounding changes, correctness still requires the controller's varied-input tolerance check. The available catalog contains only the correct 0.312358913 s baseline and no candidate diversity yet, so this is a distinct first scalar-arithmetic experiment, not a claimed speedup.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Rewrote NoiseWeight as t^3 * (t * (6*t - 15) + 10), preserving the quintic fade polynomial while testing Horner evaluation alone."
  ]
}
```

### Essai 3 · T3 · ef062539f7784946

Parent : `2af6b431524cfeeb7794f62f248cbda0b6b24ae0`. Statut mesuré : **valid**.

Hypothèse déclarée : Precomputing the eight octave-scaled y coordinates once per row replaces eight y multiplications per pixel with eight multiplications per row. Each pixel retains the original scalar x/z scaling, hash lookups, Noise evaluations, and accumulation order. The setup cost may outweigh the savings on narrow rows; this isolated reuse variant can be compared with a later isolated SIMD candidate without combining the opportunities prematurely.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Precompute the eight lambda-scaled y coordinates once per image row and reuse them across columns.",
    "Retain scalar per-pixel x/z scaling and the original Noise/hash/interpolation arithmetic; defer z reuse and SIMD for isolated comparison."
  ]
}
```

### Essai 4 · T1 · c47661bf0c474573

Parent : `2af6b431524cfeeb7794f62f248cbda0b6b24ae0`. Statut mesuré : **valid**.

Hypothèse déclarée : The previous fully factored candidate was correct and measured at 0.264444 s versus the baseline's 0.312359 s, but it changed both lookup levels. This candidate tests whether explicitly sharing only the two first-level permutation results captures useful benefit; the remaining second- and third-level lookups and all floating-point expressions stay per-corner and unchanged.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Precompute NoisePerm[ix] and NoisePerm[ix + 1] once per Noise call and reuse them across all eight gradient evaluations.",
    "Replace Grad with a helper that receives the precomputed first-level permutation value while retaining the original second- and third-level lookups, gradient selection, offsets, and floating-point interpolation expressions.",
    "Leave output traversal, ABI, and full-output overwrite behavior unchanged."
  ]
}
```

### Essai 5 · T2 · 4a9a5cce5660497f

Parent : `b3e287dab815b11d4cc47ae2757b53710dd4cda3`. Statut mesuré : **valid**.

Hypothèse déclarée : The parent already uses Horner evaluation for NoiseWeight. Changing only Lerp from (1-t)*low + t*high to low + t*(high-low) tests the alternative interpolation form independently. It may reduce arithmetic, but changed rounding requires the fixed varied-input tolerance check; no speedup is claimed before measurement.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Changed only Lerp to low + t * (high - low), retaining the parent's Horner NoiseWeight implementation."
  ]
}
```

### Essai 6 · T3 · e4f7d4c328f24f12

Parent : `2af6b431524cfeeb7794f62f248cbda0b6b24ae0`. Statut mesuré : **valid**.

Hypothèse déclarée : An OpenMP SIMD directive on the contiguous x-pixel loop may let the compiler batch independent Turbulence evaluations and amortize loop/control overhead, but the nested permutation-table lookups may require expensive gathers or inhibit useful vectorization. This isolated experiment keeps the scalar hash, arithmetic, and Turbulence forms unchanged to contrast with the measured row-y reuse variant; any benefit must outweigh vector setup and gather costs.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Add an OpenMP SIMD directive to the contiguous inner x loop, leaving the original per-pixel Turbulence, hash lookups, and arithmetic unchanged.",
    "Retain the original output indexing and full scalar iteration domain so arbitrary widths and compiler-handled tails are covered without manual batching."
  ]
}
```

### Essai 7 · T1 · 9f01e3ccd2534b37

Parent : `2af6b431524cfeeb7794f62f248cbda0b6b24ae0`. Statut mesuré : **valid**.

Hypothèse déclarée : The prior fully factored version measured faster than baseline, while explicitly factoring only the first level was close to baseline. This candidate isolates the four shared second-level permutation results: each is reused for both z planes, but the first-level expressions remain nested and repeated. If this helps, second-level reuse may account for more of the full-factor result; compiler common-subexpression elimination could also coalesce the repeated first-level expressions, so that possibility remains an unobserved factor.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replace the per-corner three-level Grad lookup with four explicitly shared second-level x/y permutation results, each reused for the lower and upper z corner hashes.",
    "Leave the first-level permutation expressions nested in each second-level result rather than explicitly sharing them, isolating second-level reuse as far as the source representation allows.",
    "Move the unchanged gradient-selection arithmetic into GradHash and preserve the existing floating-point offsets, weighting, interpolation, output traversal, ABI, and full-output overwrite behavior."
  ]
}
```

### Essai 8 · T2 · c971305fc3a54f5b

Parent : `2af6b431524cfeeb7794f62f248cbda0b6b24ae0`. Statut mesuré : **valid**.

Hypothèse déclarée : Changing only Lerp to low + t*(high-low) while retaining the original NoiseWeight form tests the interpolation alternative independently of the earlier Horner-fade change. Prior measurements suggest the combined Horner-plus-Lerp program may be faster, but do not isolate the interpolation effect; this baseline-based variant can clarify that contribution. Rounding changes require the controller's varied-input tolerance check; no speedup is claimed before measurement.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Changed only Lerp from (1-t)*low + t*high to low + t*(high-low), retaining the original NoiseWeight expression and all other source behavior."
  ]
}
```

### Essai 9 · T3 · 15645d25f2d54ea6

Parent : `f705a5068386ffceaad2e9f9b2928ce67370ba5f`. Statut mesuré : **valid**.

Hypothèse déclarée : On the selected row-y-reuse parent, precomputing the eight octave-scaled z coordinates once per image removes eight repeated z multiplications per pixel while retaining the scalar hash, Noise arithmetic, x scaling, accumulation order, and existing y reuse. Since z is image-constant, the small setup cost may amortize across pixels; this tests its incremental value without assuming it beats SIMD or the parent.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Precompute the eight octave-scaled values for the image-constant z coordinate once before the row loop.",
    "Pass the precomputed z values into the existing turbulence loop while retaining row-level scaled-y reuse and the original scalar x scaling, hash lookups, arithmetic, accumulation order, indexing, and full pixel iteration domain."
  ]
}
```

### Essai 10 · T1 · cdfe6a8a2f234171

Parent : `2af6b431524cfeeb7794f62f248cbda0b6b24ae0`. Statut mesuré : **valid**.

Hypothèse déclarée : Explicitly share both first-level permutation values and the four second-level x/y results, but leave each final z lookup inside the gradient helper. This tests whether that intermediate-sharing combination can approach the faster fully factored candidate while allowing the compiler to coalesce or schedule the final lookups; no emitted-code observation is available here.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Precompute the two first-level permutation values once for each Noise evaluation.",
    "Precompute the four x/y second-level permutation values and reuse each across both z corners.",
    "Move only the final NoisePerm lookup into GradFromXYHash, preserving the existing gradient-selection and floating-point expressions.",
    "Leave weighting, interpolation, output traversal, ABI, full output writes, and thread-budget behavior unchanged."
  ]
}
```

### Essai 11 · G · f8027a9605d642a5

Parent : `8a4c91500f9c1573eb8cfb4f71eb98a3c140ca09`. Statut mesuré : **valid**.

Hypothèse déclarée : Combining the best measured correct hash-factorization program with the independently correct Lerp rewrite may improve performance by reducing repeated permutation work and arithmetic, but the two effects have not been measured together and may interact.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Retained the T1 source's shared first-level and second-level permutation results and explicit final corner hashes; its gradient selection and NoiseWeight remain unchanged.",
    "Adapted the T2 Lerp form from (1-t)*low + t*high to low + t*(high-low), keeping the change confined to interpolation."
  ]
}
```

## popcount — job 781173

Campagne `popcount`. Pipeline achevé : **True**. Essais : 12. Commit retenu : `b0ee7ba58f17ad6800b7fa68ed8ef6dbbf3d7ae5`. Commit G : `99192ffccaf41980855989103266f9a866838867`. G confirmé : True.

Objectif naïf de recherche : 0,001045785 s ; retenu : 0,000081511 s ; G : 0,000081520 s.

Début UTC : 2026-10-23T17:14:55.150406+00:00 ; durée murale : 1937,2 s ; dépassement cible déclaré : 137,2 s.

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | 6f2e56d27c904088 | valid | 0,000081674 | dde6249b79917c78b5c6eff5a536128edecbcc8d |
| 2 | T2 | 012a1c18810646be | valid | 0,000081862 | 20c7325e3a22a1c6f20ce1636c357ffc638dc68c |
| 3 | T3 | d52584f5e58642a5 | valid | 0,000934067 | 61ca7de7079ac2e877ace91d79ca7b280fc4daae |
| 4 | T2 | e6812e6b94b04d98 | valid | 0,000435936 | 6386e1b214cc2629249b3d992c5d82a80988192b |
| 5 | T3 | 80414a41ff0347c1 | valid | 0,001131190 | b6b2d4038cf310219d7efe6bf0eca59d706b03d0 |
| 6 | T2 | 829bf476c8214cf9 | valid | 0,000081781 | 4de77c4ee3d0966541c66023b91f7c550a4de8ae |
| 7 | T1 | 94d66fa78ae2485b | valid | 0,000081758 | 2b983b1a71c5986b8204e6f4d43522f4946b920e |
| 8 | T3 | f401f13071914fe9 | valid | 0,000956882 | b567ae4f1abfb42944b2a61a7d68641480edc2a5 |
| 9 | T1 | 8c9769b516de435d | valid | 0,000081471 | b0ee7ba58f17ad6800b7fa68ed8ef6dbbf3d7ae5 |
| 10 | T2 | e8fbd25899cc4b97 | valid | 0,000392010 | 420c7de9a9972d02fec6d39e93daed196f4395b9 |
| 11 | T3 | 38aed3eb9d4c4df9 | valid | 0,000980457 | 3c85df5ed1b368086b63756dc938d6346e990052 |
| 12 | G | 0ce9f0ec31694467 | valid | 0,000081508 | 99192ffccaf41980855989103266f9a866838867 |

### Essai 1 · T1 · 6f2e56d27c904088

Parent : `0168e380b8812c87b7cf6a8227706578f9a8b4b3`. Statut mesuré : **valid**.

Hypothèse déclarée : Placing GCC's popcnt target attribute before the function declaration should compile under the frozen GCC configuration and enable hardware lowering of the compiler-recognized popcount builtin, while preserving the serial dependent update and uint32_t wraparound. The controller must verify the generated code, correctness and latency; no speedup is assumed.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Move the GCC target(\"popcnt\") attribute before the function return type so the definition can compile with the per-function POPCNT feature enabled.",
    "Retain __builtin_popcount for each uint32_t XOR value and preserve the original serial, loop-carried uint32_t accumulation."
  ]
}
```

### Essai 2 · T2 · 012a1c18810646be

Parent : `0168e380b8812c87b7cf6a8227706578f9a8b4b3`. Statut mesuré : **valid**.

Hypothèse déclarée : A fixed-operation 32-bit SWAR reduction can replace the variable-length per-bit loop and shorten the dependent update while preserving the exact uint32_t popcount and recurrence. The frozen compiler may or may not canonicalize this arithmetic to the same machine implementation as a hardware-popcount path; source code and timing alone cannot establish that.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replaced the variable-length bit-at-a-time popcount helper with a 32-bit SWAR reduction using pair, two-bit, and nibble reductions followed by byte-lane multiplication.",
    "Kept the same input XOR, uint32_t accumulator, nested loop order, and recurrence update."
  ]
}
```

### Essai 3 · T3 · d52584f5e58642a5

Parent : `0168e380b8812c87b7cf6a8227706578f9a8b4b3`. Statut mesuré : **valid**.

Hypothèse déclarée : Replacing the indexed inner loop with pointer traversal and four explicitly ordered updates per loop body may reduce index and branch overhead. The naive popcount is unchanged, so any measured difference from the supplied baseline isolates this loop-control candidate; the recurrence still updates result after each element in the original pass/element order. If its standalone gain is small, it may still be worth testing alongside a fast-popcount candidate.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replace the indexed inner loop with a pointer cursor and an integer remaining-element count, avoiding a flattened dimension product.",
    "Unroll four recurrence updates in their original order, then process any remainder sequentially.",
    "Keep popcount_naive unchanged so this experiment isolates loop-control changes."
  ]
}
```

### Essai 4 · T2 · e6812e6b94b04d98

Parent : `20c7325e3a22a1c6f20ce1636c357ffc638dc68c`. Statut mesuré : **valid**.

Hypothèse déclarée : A multiplication-free SWAR reduction using pair, two-bit, and nibble sums followed by byte and halfword folds may trade the parent's final multiply for additional additions. Measuring this contrasting scalar implementation tests whether that tradeoff helps and whether the frozen compiler lowers it like the prior SWAR or hardware-popcount path; source and timing alone cannot establish identical machine code.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replaced the prior subtract-and-multiply SWAR reduction with pair, two-bit, and nibble additions followed by byte and halfword folds.",
    "Kept the input XOR, uint32_t accumulator, nested loop order, and recurrence update unchanged."
  ]
}
```

### Essai 5 · T3 · 80414a41ff0347c1

Parent : `0168e380b8812c87b7cf6a8227706578f9a8b4b3`. Statut mesuré : **valid**.

Hypothèse déclarée : The earlier pointer-traversal plus four-update unrolling candidate was correct and measured at 0.9341 ms versus the 1.0478 ms baseline, but that combined change does not show whether pointer traversal alone helped. This candidate keeps the naive popcount and exact recurrence order, replaces indexed inner-loop access with a pointer and remaining-element count, and omits unrolling to isolate that loop-control change. It avoids flattened-count arithmetic and overwrites output on every call; its performance remains to be measured.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replace indexed inner-loop accesses with a pointer cursor and remaining-element count, avoiding flattened dimension arithmetic.",
    "Use one recurrence update per loop iteration, with no unrolling, to contrast with the prior pointer-plus-four-update candidate.",
    "Keep popcount_naive unchanged and preserve the serial pass/element recurrence order; initialize and store the result on every call."
  ]
}
```

### Essai 6 · T2 · 829bf476c8214cf9

Parent : `0168e380b8812c87b7cf6a8227706578f9a8b4b3`. Statut mesuré : **valid**.

Hypothèse déclarée : Counting set bits by repeatedly clearing the least-significant set bit makes the work proportional to the input's population count rather than its bit width. It may beat the baseline's bit-at-a-time loop for typical values, but the data-dependent loop may be slower than fixed-operation SWAR. If GCC recognizes this idiom as a hardware popcount, generated assembly—not timing alone—would establish that; correctness and recurrence semantics remain unchanged for every uint32_t input.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replaced the per-bit right-shift popcount loop with a loop that clears the lowest set bit and increments a uint32_t count.",
    "Preserved the recurrence expression, accumulator type, and nested iteration order."
  ]
}
```

### Essai 7 · T1 · 94d66fa78ae2485b

Parent : `0168e380b8812c87b7cf6a8227706578f9a8b4b3`. Statut mesuré : **valid**.

Hypothèse déclarée : Replacing the compiler builtin with a direct 32-bit x86 POPCNT inline-assembly operation should make the intended hardware instruction explicit for every XOR value while retaining the serial result dependency and uint32_t wraparound. Its opaque implementation may match or regress against GCC's previously successful builtin path; no speedup is assumed.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replace the naive popcount helper with a 32-bit POPCNT inline-assembly helper.",
    "Use that helper for each a[i] XOR result while preserving iteration order and the serial uint32_t accumulation."
  ]
}
```

### Essai 8 · T3 · f401f13071914fe9

Parent : `61ca7de7079ac2e877ace91d79ca7b280fc4daae`. Statut mesuré : **valid**.

Hypothèse déclarée : The pointer-plus-four-update parent was faster than baseline, while the pointer-only variant was slower, so the contribution of pointer traversal versus unrolling is unresolved. This candidate keeps the same naive popcount and four explicitly ordered updates but uses indexed array access; comparing it with the pointer-plus-four parent tests whether pointer traversal adds benefit beyond ordered unrolling.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Keep popcount_naive unchanged so the candidate tests loop traversal only.",
    "Replace the pointer cursor with an integer index and explicitly perform four ordered recurrence updates per block, followed by a sequential tail.",
    "Retain per-pass traversal, exact element/update order, and output initialization on every call; do not flatten dimensions or parallelize the recurrence."
  ]
}
```

### Essai 9 · T1 · 8c9769b516de435d

Parent : `0168e380b8812c87b7cf6a8227706578f9a8b4b3`. Statut mesuré : **valid**.

Hypothèse déclarée : The prior target-attributed builtin and inline-assembly candidates were both correct at about 81.7 microseconds versus the baseline's 1.048 milliseconds, but the observations do not include disassembly. This candidate keeps the compiler-recognized popcount path and explicitly unrolls four sequential updates to test whether inner-loop control overhead remains significant after popcount lowering. No additional speedup is assumed; the controller must verify the build, lowering, correctness, and official latency.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replace the bit-by-bit helper with GCC's builtin popcount under a per-function popcnt target attribute.",
    "Unroll the inner loop in groups of four while retaining four sequential, result-dependent updates and a generic remainder loop.",
    "Keep the outer iteration order, output contract, unsigned 32-bit accumulation, and thread usage unchanged."
  ]
}
```

### Essai 10 · T2 · e8fbd25899cc4b97

Parent : `6386e1b214cc2629249b3d992c5d82a80988192b`. Statut mesuré : **valid**.

Hypothèse déclarée : A distinct nibble-wise subtractive SWAR identity, followed by byte folding and multiplication, may lower differently from the parent's add-and-fold reduction while preserving exact uint32_t popcount. Measure it against the baseline and prior popcount paths; source and timing alone cannot establish identical machine code.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replaced the parent's pair/two-bit/nibble additions and unmasked byte/halfword folds with isolated per-nibble subtractive counting, then folded byte counts and multiplied to obtain the total.",
    "Kept the input XOR, uint32_t accumulator, nested loop order, and recurrence update unchanged."
  ]
}
```

### Essai 11 · T3 · 38aed3eb9d4c4df9

Parent : `0168e380b8812c87b7cf6a8227706578f9a8b4b3`. Statut mesuré : **valid**.

Hypothèse déclarée : A pointer walk with two explicitly ordered recurrence updates per iteration may reduce loop-control overhead versus the indexed baseline while avoiding the larger unroll factor of the prior pointer-plus-four variant. The naive popcount remains unchanged, isolating this loop-control experiment; its performance is unmeasured.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Keep popcount_naive unchanged to isolate loop-control changes.",
    "Replace indexed inner traversal with pointer traversal and two explicitly ordered recurrence updates per iteration, followed by a single-element tail when needed.",
    "Preserve pass and element order, avoid flattened dimension products, and overwrite output on every call."
  ]
}
```

### Essai 12 · G · 0ce9f0ec31694467

Parent : `b0ee7ba58f17ad6800b7fa68ed8ef6dbbf3d7ae5`. Statut mesuré : **valid**.

Hypothèse déclarée : The selected T1 candidate's speed may come primarily from target-attributed popcount rather than manual four-way unrolling. Retain its popcount path but use a simple sequential inner loop to test whether explicit unrolling is beneficial, while preserving the loop-carried recurrence and exact uint32_t result.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Retain the target-attributed GCC builtin popcount from T1.",
    "Replace four-way manual unrolling and the remainder loop with one ordered indexed inner loop.",
    "Preserve the input order, recurrence dependency, uint32_t wraparound, full output write, and sequential execution."
  ]
}
```

## raytracer — job 781193

Campagne `raytracer`. Pipeline achevé : **True**. Essais : 11. Commit retenu : `9566a6000f050a2489c4baa16ad2f0533be686db`. Commit G : `fc387887531dd17a80ece6235826a6d5c6ebb078`. G confirmé : True.

Objectif naïf de recherche : 0,233734141 s ; retenu : 0,043961142 s ; G : 0,044747251 s.

Début UTC : 2026-10-23T18:02:52.345843+00:00 ; durée murale : 1297,5 s ; dépassement cible déclaré : 0,0 s.

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | 6ff0df4221054272 | valid | 0,045537528 | 8c5be9198295c52e39b42550acba956fd6d0c273 |
| 2 | T2 | 25d67aa491fa482d | valid | 0,229307478 | 6b4b21e6cb46dd009614013ca99ad0a936680044 |
| 3 | T3 | 3ab1a4f7cb7a4bc0 | infrastructure_error | NR | — |
| 4 | T2 | c546a8d5525440fe | valid | 0,228316839 | 7ec50fbc9747406fc92412255085b627a3222081 |
| 5 | T1 | 2052f213b5eb456f | valid | 0,049574022 | db934a282809bcaade06d374129216a25920c828 |
| 6 | T2 | 6e108e6dc39d42d5 | valid | 0,233339682 | 7376ee7a63c65b99297c36a71b78a36fe0e70403 |
| 7 | T1 | 90a8f3292b7645d9 | valid | 0,049548237 | 2fc36f0ade7a226773333200146f62c3c3d8445a |
| 8 | T1 | 778e678a696041e2 | valid | 0,046115480 | d1566fb8fa8b41c410ab1542e7bd811f8e59cd55 |
| 9 | G | 41b200081ac54317 | valid | 0,044361360 | 63dbda2ca41fa10a2df6d0386ea7c32a1b8da852 |
| 10 | G | 6286d433b26c4922 | valid | 0,043958860 | 9566a6000f050a2489c4baa16ad2f0533be686db |
| 11 | G | 6cb920f7b3f5473a | valid | 0,044746625 | fc387887531dd17a80ece6235826a6d5c6ebb078 |

### Essai 1 · T1 · 6ff0df4221054272

Parent : `a2cc335bd726da1922eb35d8efcd48fa74d4c74e`. Statut mesuré : **valid**.

Hypothèse déclarée : Dynamic scheduling of independent rows with chunk size 1 should balance row-to-row variation in BVH traversal cost while preserving each pixel's ray generation and traversal order. The thread budget is capped by the number of rows; this tests row-level dynamic scheduling, not a performance result.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Parallelized the outer row loop with OpenMP dynamic scheduling, chunk size 1, when OpenMP is enabled.",
    "Bound the requested worker count to at least one and at most the row count; retained a serial fallback when OpenMP is not enabled.",
    "Passed the threads budget through the existing run entry point without changing its ABI."
  ]
}
```

### Essai 2 · T2 · 25d67aa491fa482d

Parent : `a2cc335bd726da1922eb35d8efcd48fa74d4c74e`. Statut mesuré : **valid**.

Hypothèse déclarée : Replacing the temporary float3 slab calculations with explicit scalar axis calculations may reduce hot-path construction and data-movement overhead. Keeping the same arithmetic order, swap tests, std::max/std::min argument order, and final inclusive comparison preserves bounds acceptance. A pointer-based pending-node stack may reduce repeated node-index addressing while retaining the existing 64-entry capacity, split-axis choice, traversal order, and primitive visitation order. Performance improvement is a hypothesis for controller measurement, not an established result.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Compute each bounding-box slab directly from scalar bounds, origin, and inverse-direction components, preserving the original per-axis operation order and inclusive acceptance test.",
    "Represent the BVH current node and 64 pending stack entries as node pointers while preserving split-axis ordering and primitive visitation."
  ]
}
```

### Essai 3 · T3 · 3ab1a4f7cb7a4bc0

Parent : `a2cc335bd726da1922eb35d8efcd48fa74d4c74e`. Statut mesuré : **infrastructure_error**.

Diagnostic : Codex attempted a tool call outside the authorized MCP access

### Essai 4 · T2 · c546a8d5525440fe

Parent : `6b4b21e6cb46dd009614013ca99ad0a936680044`. Statut mesuré : **valid**.

Hypothèse déclarée : The current BBoxIntersect source interleaves independent slab-endpoint arithmetic with a dependent t0/t1 update chain. Calculating the same six endpoints first may let the compiler overlap their latency before that chain, reducing node-test cost. Endpoint expressions, per-axis swap tests, std::max/std::min argument order, inclusive final comparison, and BVH traversal remain unchanged; any speed effect is unmeasured.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "In BBoxIntersect, calculate the unchanged X, Y, and Z near/far slab endpoints before applying the existing ordered interval updates. Keep endpoint arithmetic, swap conditions, reduction argument order, inclusive acceptance, and the BVH node walk unchanged."
  ]
}
```

### Essai 5 · T1 · 2052f213b5eb456f

Parent : `a2cc335bd726da1922eb35d8efcd48fa74d4c74e`. Statut mesuré : **valid**.

Hypothèse déclarée : Static contiguous row scheduling should reduce row-dispatch overhead relative to the prior dynamic, chunk-1 schedule. It may lose some load balance if BVH traversal cost varies strongly by row. The ray-generation and BVH traversal body for each pixel stays unchanged.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Parallelized the existing outer row loop with OpenMP schedule(static), assigning contiguous row blocks by default.",
    "Capped the requested OpenMP team size to at least one and at most the row count, using threads as the requested maximum.",
    "Kept each pixel's ray generation, BVH traversal, and output writes unchanged; preserved the run ABI and serial fallback."
  ]
}
```

### Essai 6 · T2 · 6e108e6dc39d42d5

Parent : `a2cc335bd726da1922eb35d8efcd48fa74d4c74e`. Statut mesuré : **valid**.

Hypothèse déclarée : The catalog shows two correct, distinct variants: endpoint hoisting measured 0.2283 s and scalar slabs plus a pointer stack measured 0.2293 s, versus the 0.2369 s baseline. This candidate tests a different BBoxIntersect mechanism: use the ray's precomputed dirIsNeg bit to order endpoints directly for finite negative inverse directions, avoiding the endpoint-order comparison there. Keep the same endpoint expressions, X/Y/Z interval-update order, std::max/std::min argument order, inclusive final test, and BVH walk; retain the original compare/swap path for other cases, including negative infinite inverse directions.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replace temporary float3 slab calculations with six scalar endpoint calculations while retaining the existing per-axis arithmetic expressions and X/Y/Z reduction order.",
    "Use the precomputed direction sign to swap endpoints directly for negative finite inverse directions; use the original compare-and-swap logic otherwise, preserving the ordered std::max/std::min updates and inclusive final comparison."
  ]
}
```

### Essai 7 · T1 · 90a8f3292b7645d9

Parent : `a2cc335bd726da1922eb35d8efcd48fa74d4c74e`. Statut mesuré : **valid**.

Hypothèse déclarée : Guided row scheduling with minimum chunk 1 is a contrasting third schedule: it may reduce dispatch overhead versus dynamic chunk-1 scheduling while shrinking chunks as work remains to help with uneven BVH traversal. Prior evidence shows dynamic rows measured 0.04554 s and static rows 0.04957 s, but it does not establish behavior at 1, 4, and 40 threads separately; guided remains an unmeasured hypothesis.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Added a parallel rendering helper that uses threads as a maximum, bounded to at least one and no more than the image height.",
    "Applied OpenMP guided scheduling with a minimum chunk of one row; retained the existing per-pixel ray generation, traversal sequence, and once-per-pixel output writes.",
    "Preserved the run entry-point ABI and retained the original raytrace_serial helper signature as a one-thread wrapper."
  ]
}
```

### Essai 8 · T1 · 778e678a696041e2

Parent : `a2cc335bd726da1922eb35d8efcd48fa74d4c74e`. Statut mesuré : **valid**.

Hypothèse déclarée : The catalog contains three distinct valid row schedules: dynamic chunk-1 measured 0.04554 s, while static contiguous and guided measured about 0.04955 s; the baseline measured 0.23693 s. These aggregate measurements do not establish performance separately at 1, 4, and 40 threads. This candidate tests whether cyclic static row assignment (chunk 1) balances row-to-row traversal variation without dynamic-scheduler dispatch overhead, unlike the earlier contiguous static schedule.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Added a parallel rendering helper that caps the requested worker count to at least one and at most the image height.",
    "Applied OpenMP static scheduling with a chunk size of one row, assigning rows cyclically; left per-pixel ray generation, BVH traversal, and unique output writes unchanged.",
    "Retained the raytrace_serial signature as a one-thread wrapper and preserved the run ABI, with a serial fallback when OpenMP is unavailable."
  ]
}
```

### Essai 9 · G · 41b200081ac54317

Parent : `8c5be9198295c52e39b42550acba956fd6d0c273`. Statut mesuré : **valid**.

Hypothèse déclarée : Combining dynamic one-row OpenMP scheduling with T2's independent scalar slab-endpoint hoisting may reduce total render time by exposing parallelism while improving per-ray box-test throughput. The standalone measurements suggest both ideas are worth testing but do not establish additive benefit.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Kept T1's OpenMP parallel outer-row loop with dynamic scheduling, chunk size 1, and worker count capped by the requested budget and image height.",
    "Integrated T2's calculation of all six scalar slab endpoints before the unchanged ordered X/Y/Z interval updates.",
    "Used T2's pointer-based traversal stack while retaining child order, primitive visitation, ray generation, and triangle-intersection logic."
  ]
}
```

### Essai 10 · G · 6286d433b26c4922

Parent : `63dbda2ca41fa10a2df6d0386ea7c32a1b8da852`. Statut mesuré : **valid**.

Hypothèse déclarée : The integrated candidate already hoists slab endpoints and parallelizes rows. Using ray.dirIsNeg to select the endpoint order for finite negative inverse directions may avoid a comparison in each affected box test, while the original comparison remains as a fallback for other cases. The T2 variant was slower standalone, so this is a test for an interaction with the faster threaded base, not an assumed improvement.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Retained the integrated candidate's OpenMP dynamic row scheduling with the requested worker budget capped by image height.",
    "Retained the scalar-hoisted bounding-box endpoints and pointer-based BVH stack from the selected integrated base.",
    "Added direction-sign endpoint ordering for finite negative inverse directions, falling back to the original endpoint comparison otherwise; preserved the ordered interval reductions and ray/triangle traversal semantics."
  ]
}
```

### Essai 11 · G · 6cb920f7b3f5473a

Parent : `9566a6000f050a2489c4baa16ad2f0533be686db`. Statut mesuré : **valid**.

Hypothèse déclarée : Static cyclic row assignment may avoid dynamic scheduling overhead in the current threaded renderer, while the optimized BVH path may change the balance of work across rows. The standalone static candidate was slightly slower than dynamic, so this comparison tests for an interaction rather than assuming static is better.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Retained dynamic integrated candidate's scalar slab endpoints, direction-sign fallback, pointer stack, and thread-budget cap.",
    "Changed the OpenMP outer-row schedule from dynamic chunk 1 to static chunk 1, following the valid cyclic-static T1 candidate.",
    "Preserved per-pixel ray generation, BVH and triangle intersection rules, unique output writes, and the run ABI."
  ]
}
```

## reduction — job 781178

Campagne `reduction`. Pipeline achevé : **True**. Essais : 4. Commit retenu : `bc06b33364947603b1dd1de4e586350d914e2a16`. Commit G : `bc06b33364947603b1dd1de4e586350d914e2a16`. G confirmé : True.

Objectif naïf de recherche : 0,000046732 s ; retenu : 0,000006920 s ; G : 0,000006920 s.

Début UTC : 2026-10-23T17:21:21.229102+00:00 ; durée murale : 1957,5 s ; dépassement cible déclaré : 157,5 s.

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | c8b4f90afeec4ebf | valid | 0,000006782 | 7cb3b9853cc488ed91aea499da2f09ab04fc14e7 |
| 2 | T2 | 28fe8ede883b4706 | valid | 0,001028211 | 9885beaebb7c8093c30f0001b80325bfde30c97c |
| 3 | T3 | cf2b44f0445c4cef | valid | 0,000007048 | 81dbcc2cd2d67de706d704674ced5a362098c235 |
| 4 | G | ee7dab3f17704fd9 | valid | 0,000006906 | bc06b33364947603b1dd1de4e586350d914e2a16 |

### Essai 1 · T1 · c8b4f90afeec4ebf

Parent : `df3abc2bcfa7d21328e31125c0ee5c1a653524bd`. Statut mesuré : **valid**.

Hypothèse déclarée : Pour les grandes entrées, 256 threads accumulant 8 valeurs coalescées chacun devraient réduire le nombre de lancements de quatre réductions successives plus une copie à deux kernels, avec seulement un partiel écrit par CTA. Cette proposition teste la variante personnalisée warp/shuffle via warpReduceSum; une variante jumelle CUB BlockReduce devra être mesurée séparément pour comparer les primitives. Les petits n passent par un kernel direct (n=1 conserve la copie existante). Aucun gain n'est présumé avant mesure.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacement de la chaîne de réductions et copie finale par une réduction à deux passes pour n > 2048 : CTA de 256 threads traitant des tuiles de 2048 éléments et écrivant un partiel chacun dans scratch.",
    "Réduction intra-bloc personnalisée par warpReduceSum et une synchronisation bloc pour agréger les sommes de warps.",
    "Ajout d'un chemin direct à un kernel pour n <= 2048 et conservation de la copie device-to-device pour n == 1.",
    "Calcul du nombre de partiels sans addition susceptible de déborder; chaque lecture d'entrée ou de partiel est bornée et chaque emplacement scratch lu est écrit durant l'appel."
  ]
}
```

### Essai 2 · T2 · 28fe8ede883b4706

Parent : `df3abc2bcfa7d21328e31125c0ee5c1a653524bd`. Statut mesuré : **valid**.

Hypothèse déclarée : For n larger than one CTA, a single occupancy-capped cooperative launch may beat the baseline's repeated reduction launches and final device copy. Each CTA computes grid-stride 64-bit partial sums, the grid synchronizes, and CTA 0 writes the result. Runtime capability, occupancy, and launch checks gate this route; global synchronization and setup overhead may still erase any benefit, so the controller must measure it.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Add a grid-stride cooperative reduction kernel that writes 64-bit CTA partials, performs a Cooperative Groups grid sync, and lets CTA 0 produce out.",
    "Query runtime cooperative-launch support and kernel occupancy; cap the grid at activeBlocksPerSM times multiprocessor count and fall back if the cooperative launch is unavailable or rejected.",
    "Keep the existing multistage reduction and copy path for small inputs and as the correctness fallback."
  ]
}
```

### Essai 3 · T3 · cf2b44f0445c4cef

Parent : `df3abc2bcfa7d21328e31125c0ee5c1a653524bd`. Statut mesuré : **valid**.

Hypothèse déclarée : Une réduction par CTA sur des tranches de 4096 éléments, avec sommes locales et partiels en int64 puis atomicAdd unsigned modulo 2^32 dans out, pourrait réduire le coût des lancements hiérarchiques. La remise à zéro de out dans le flux par défaut précède les atomiques; leur contention reste un compromis à mesurer face à l'alternative int64 en scratch avec conversion finale.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer la réduction hiérarchique par un seul kernel qui calcule une somme int64 par CTA sur une tranche de 4096 éléments.",
    "Réinitialiser explicitement out via cudaMemsetAsync dans le flux par défaut puis atomically accumuler chaque partiel après conversion unsigned modulo 2^32.",
    "Laisser scratch inutilisé afin de tester la variante d'accumulation directe dans out, sans allocation supplémentaire ni kernel de finalisation."
  ]
}
```

### Essai 4 · G · ee7dab3f17704fd9

Parent : `7cb3b9853cc488ed91aea499da2f09ab04fc14e7`. Statut mesuré : **valid**.

Hypothèse déclarée : Adapter les tuiles de 2048 à 4096 valeurs dans la réduction hiérarchique mesurée de T1 peut diviser par deux le nombre de partiels et le travail du dernier kernel. La réduction finale élargie à 64 bits protège les sommes intermédiaires, puisque seul le résultat réel est garanti int32. Le gain de performance n’est pas établi avant mesure.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Conserver la réduction hiérarchique à deux passes de T1, ses chemins pour petites entrées et sa réduction warp personnalisée.",
    "Passer le nombre d’éléments traités par thread de 8 à 16 : 256 threads forment désormais une tuile de 4096 valeurs, réduisant le nombre de partiels pour les grandes entrées.",
    "Effectuer l’accumulation finale en long long et convertir le résultat en int32 une fois, afin de préserver l’exactitude lorsque les sommes intermédiaires dépassent int32."
  ]
}
```

## s4convd — job 781179

Campagne `s4convd`. Pipeline achevé : **True**. Essais : 5. Commit retenu : `c72ee5545644b220d0e779756c27a952d8b9f857`. Commit G : `c72ee5545644b220d0e779756c27a952d8b9f857`. G confirmé : True.

Objectif naïf de recherche : 0,035426254 s ; retenu : 0,015289505 s ; G : 0,015289505 s.

Début UTC : 2026-10-23T17:21:33.200808+00:00 ; durée murale : 1798,8 s ; dépassement cible déclaré : 0,0 s.

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | bd0870181d4448d5 | valid | 0,034272620 | 73a7294aff03e38d3ca0f4d8cad15e26bcb01ea0 |
| 2 | T2 | dcdcd3e1866746be | valid | 0,039650172 | 66f5e6fbdffef8954834ad35fe2bfbf23d9a5bd3 |
| 3 | T3 | 831cc8b3e98541af | valid | 0,016496879 | 0cf03986164dac4257ba2b16fc408fc9ec588336 |
| 4 | T4 | 9ba84a142ade4fd3 | valid | 0,021236328 | cda94546aff975eb9be62b2618b6eb1ffda6667a |
| 5 | G | df7cef165725436e | valid | 0,015334215 | c72ee5545644b220d0e779756c27a952d8b9f857 |

### Essai 1 · T1 · bd0870181d4448d5

Parent : `f954b0660a895021f1d752ff1918b2e2f046c67c`. Statut mesuré : **valid**.

Hypothèse déclarée : The valid baseline is correct and has a measured mean full-call time of 0.0354793 s (baseline-e1). Its forward and gx kernels launch separately with one 256-thread CTA per row, while the supplied workload has L=48. Fusing both direct-tap calculations into a flat-output grid should reduce launch and under-filled-CTA costs, though the runtime index divisions may offset some benefit. This bundles fusion and mapping changes; no speedup is assumed.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Fuse forward and gx computation into one kernel while preserving each output's tap order, padding bounds, and reversed gx taps.",
    "Map threads over a generic flattened output range with grid-stride handling, retaining direct per-output tap loads rather than explicit stencil input reuse.",
    "Leave the gk kernel and its launch unchanged; write fresh forward and gx outputs for every processed element."
  ]
}
```

### Essai 2 · T2 · dcdcd3e1866746be

Parent : `f954b0660a895021f1d752ff1918b2e2f046c67c`. Statut mesuré : **valid**.

Hypothèse déclarée : Staging short tap chunks of x and gy in shared memory should reduce repeated global input loads in the forward and gx stencils while retaining the existing grid, block mapping, tap order, full-FP32 arithmetic, and gk kernel. Correctness and full-call speedup remain unmeasured; the unchanged gk work may limit the overall impact.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Stage each input row's tap neighborhood in a 287-float shared-memory tile, refilled in chunks of at most 32 taps.",
    "Reuse the staged x tile for forward and the staged gy tile for gx, preserving ascending tap accumulation and gx's reversed coefficient index.",
    "Retain the existing kernel launches, grid/block mapping, and gk implementation."
  ]
}
```

### Essai 3 · T3 · 831cc8b3e98541af

Parent : `f954b0660a895021f1d752ff1918b2e2f046c67c`. Statut mesuré : **valid**.

Hypothèse déclarée : A no-scratch gk reduction with one 256-thread CTA per (h,j) distributes the B*L products across lanes and tree-reduces them, replacing each coefficient's serial scan with batch/time parallelism. This may reduce gk latency without partial-buffer traffic or a second reduction launch; the changed FP32 reduction order and increased CTA count require correctness and full-call timing validation. Forward and gx remain unchanged.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Replace the gk kernel with one CTA per (h,j); lanes grid-stride over B*L positions, then reduce their FP32 sums in shared memory.",
    "Keep forward and gx kernels and launch mappings unchanged; avoid scratch storage and overwrite every gk coefficient on each call."
  ]
}
```

### Essai 4 · T4 · 9ba84a142ade4fd3

Parent : `f954b0660a895021f1d752ff1918b2e2f046c67c`. Statut mesuré : **valid**.

Hypothèse déclarée : The existing per-coefficient gk path serially traverses B×L for each tap. A CTA per channel and four-tap group can instead parallelize positions across lanes, cooperatively stage gy and the overlapping x interval in shared memory, and reuse that tile across adjacent taps. This may improve gk parallelism and input reuse without scratch; FP32 reduction order changes, so correctness and full-call timing remain for controller validation against the direct-load baseline.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Kept forward and gx kernels and their launch configuration unchanged.",
    "Replaced gk computation with one CTA per channel and group of four adjacent taps; each lane accumulates positions across runtime batches and length.",
    "Cooperatively loaded a gy tile and the x interval needed by the tap group into shared memory, reusing overlapping row data across taps while preserving zero-valued boundary contributions.",
    "Reduced four per-tap lane accumulators explicitly in shared memory and wrote each valid gk coefficient exactly once; used no scratch or atomics."
  ]
}
```

### Essai 5 · G · df7cef165725436e

Parent : `0cf03986164dac4257ba2b16fc408fc9ec588336`. Statut mesuré : **valid**.

Hypothèse déclarée : Combining T1's fused flat-output forward/gx kernel with T3's parallel per-coefficient gk reduction may improve on T3's 16.497 ms full-call time: T1 changes forward/gx, while T3 changes only gk. Their individually measured results do not establish the combined program's speed or correctness, so the controller must evaluate it independently.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Fused forward and gx into one generic flattened-output kernel, retaining direct tap loads and the original zero-padding and coefficient order.",
    "Retained T3's one-CTA-per-(h,j) batch/time parallel gk reduction with shared-memory FP32 reduction and no scratch accumulation."
  ]
}
```

## sgemm — job 781115

Campagne `sgemm`. Pipeline achevé : **False**. Essais : 15. Commit retenu : `333cfd136707d8ec68b4f134f90a5a24f6b2be25`. Commit G : `7c0c0c85e7fb6452fefbb195e643987fbf72086e`. G confirmé : True.

Objectif naïf de recherche : 0,275579211 s ; retenu : 0,005601954 s ; G : 0,006133908 s.

Erreur de pipeline : ForestError: Submission requires a Makefile and run.sh in the imported repository

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | 18978570d64d45e2 | valid | 0,023400213 | 82cfa263268f96ba14f36cd66469811f8f87e025 |
| 2 | T2 | f069e2e5cea7467b | valid | 0,017417722 | 98769744973826250acc786a862544327cd886db |
| 3 | T1 | fd9547ddb0d746ed | valid | 0,015545599 | cd122f6018c6f6f67d3ab69590c63f143a031ef9 |
| 4 | T2 | 689609324fde4a49 | generation_failed | NR | — |
| 5 | T1 | afbb82b143884e95 | valid | 0,008954533 | 23e5431498dbf9b8626ed9b5a546cf9160a30414 |
| 6 | T1 | ec502f4e93bc4dc1 | valid | 0,007710843 | 91f0b6f6356d29d698a0922a683180b5858b3893 |
| 7 | T2 | 14f2f4326e124c07 | valid | 0,015454465 | f1494dc881dc228afaec1db1c0981b6c3a882ec7 |
| 8 | T1 | 183d1640ebcb41df | valid | 0,007418744 | 62b01a08597a69152d8c7d32dd8dd7136503ab38 |
| 9 | T1 | 5a1dd9c855e94843 | valid | 0,006470737 | 8a82adb4423c2a941ba6c90415bcd69e4dc027c3 |
| 10 | T1 | ca8357016cdf403b | valid | 0,007178363 | e8098d3b4f92b0b70bcf584931759ec9c0332d7f |
| 11 | T1 | 5af0d39a8d7b47bb | valid | 0,022778479 | ac63e366063ac8ee3a743021382f4ec4f2da3bd6 |
| 12 | T2 | 86d5e6d40a8149a3 | valid | 0,015510112 | 288cda83ef6036103a8413861d160051a18a107c |
| 13 | T1 | 78ad9dfc98a949df | valid | 0,005576025 | 333cfd136707d8ec68b4f134f90a5a24f6b2be25 |
| 14 | T1 | 7868e8c5898c435e | valid | 0,005707840 | 4e7ffaf42cd5e7642a1250068d4fd6b3465457ec |
| 15 | G | ab3d43a2d9d74803 | valid | 0,006129861 | 7c0c0c85e7fb6452fefbb195e643987fbf72086e |

### Essai 1 · T1 · 18978570d64d45e2

Parent : `7b87d96031c1a558c1facf176fc3f388a457162a`. Statut mesuré : **valid**.

Hypothèse déclarée : Affecter les colonnes de C aux lanes contiguës du warp devrait améliorer la coalescence des lectures de B et des écritures de C. Garder le bloc 32x32, le calcul par sortie et l’ordre de réduction inchangés isole le mapping, sans mémoire partagée ni réutilisation explicite.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer le mapping où les lanes varient sur les lignes par un mapping où threadIdx.x indexe la colonne et les lanes accèdent à des colonnes row-major contiguës.",
    "Conserver une sortie par thread, une réduction séquentielle sans mémoire partagée, les bornes, et l'application unique de alpha et beta; ne pas ajouter d'allocation."
  ]
}
```

### Essai 2 · T2 · f069e2e5cea7467b

Parent : `7b87d96031c1a558c1facf176fc3f388a457162a`. Statut mesuré : **valid**.

Hypothèse déclarée : Le parent naïf n’offre pas de contrôle SIMT apparié pour isoler le coût de TMA. Ce candidat établit d’abord un kernel synchrone avec un mapping coalescé, une tuile de sortie 32×32, un panneau K de 32 et le calcul FP32 inchangé; le candidat TMA suivant pourra remplacer uniquement le chargement en conservant ces paramètres. Le catalogue T2 n’a encore aucun candidat mesuré ni diversité de source. Le kernel de référence baseline-e1 est correct et ses trois temps sont 0,275563537598, 0,275566192627 et 0,275562530518 s (moyenne 0,275564086914 s). Aucun gain du présent candidat n’est encore mesuré.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacement du calcul naïf par une multiplication SIMT en tuiles partagées 32×32 avec panneaux K de 32.",
    "Mapping des lanes le long des colonnes afin de coalescer les accès row-major; bords gérés par masquage et remplissage nul des panneaux.",
    "Conservation de l’accumulation FP32 en ordre K, de alpha/beta et de l’interface existante, sans allocation supplémentaire."
  ]
}
```

### Essai 3 · T1 · fd9547ddb0d746ed

Parent : `7b87d96031c1a558c1facf176fc3f388a457162a`. Statut mesuré : **valid**.

Hypothèse déclarée : Le candidat direct avec colonnes contiguës par lane a déjà été mesuré correct et nettement plus rapide que le baseline. En conservant ce mapping et le bloc 32x32, charger des tuiles A/B en mémoire partagée devrait réduire les lectures globales redondantes; les synchronisations pourraient toutefois annuler une partie du gain. Cette variante teste l’effet de la réutilisation sans changer la taille des tuiles ni l’application de alpha/beta.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer le kernel direct par un kernel 32x32 qui charge des tuiles A et B en mémoire partagée; remplir de zéros les éléments hors limites et synchroniser avant et après le calcul de chaque tuile K.",
    "Affecter threadIdx.x aux colonnes contiguës et inverser le lancement de la grille pour que les blocs couvrent les colonnes sur x et les lignes sur y.",
    "Garder une accumulation FP32 dans l’ordre K, puis appliquer alpha et beta une seule fois par élément de C; n’ajouter aucune allocation."
  ]
}
```

### Essai 4 · T2 · 689609324fde4a49

Parent : `98769744973826250acc786a862544327cd886db`. Statut mesuré : **generation_failed**.

Diagnostic : Documentation action ended without a subsequent source proposal

### Essai 5 · T1 · afbb82b143884e95

Parent : `7b87d96031c1a558c1facf176fc3f388a457162a`. Statut mesuré : **valid**.

Hypothèse déclarée : Le kernel partagé 32x32 mesuré est plus rapide que le kernel direct, mais conserve une sortie par thread. Cette variante teste un tuilage 64x32x16 avec 8 accumulateurs par thread : chaque valeur B chargée est réutilisée sur huit lignes de sorties, tandis que les lanes gardent des colonnes contiguës. Cela devrait réduire le travail de chargement et le nombre de threads par tuile, au prix d’un usage accru des registres; aucun gain n’est présumé avant mesure.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer le calcul direct par un kernel partagé à tuiles A[64][16] et B[16][32], avec remplissage par zéro des bords et synchronisation à chaque étape K.",
    "Utiliser des blocs de 32x8 threads où threadIdx.x parcourt les colonnes contiguës; chaque thread accumule huit lignes de sorties dans des registres et réutilise la valeur B correspondante.",
    "Garder l’accumulation FP32, appliquer alpha et beta une fois par élément de C, écrire toutes les sorties valides et ne réaliser aucune allocation."
  ]
}
```

### Essai 6 · T1 · ec502f4e93bc4dc1

Parent : `7b87d96031c1a558c1facf176fc3f388a457162a`. Statut mesuré : **valid**.

Hypothèse déclarée : Parmi les trois programmes distincts mesurés, le kernel 64x32x16 avec huit accumulateurs par thread est le plus rapide. Cette variante conserve son mapping, son bloc 32x8 et ses huit accumulateurs, mais double seulement la profondeur K de 16 à 32. Elle teste si moins d’itérations et de synchronisations compense le passage de 6 à 12 KiB de mémoire partagée par bloc; le résultat de performance reste à mesurer.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer le kernel direct par un tuilage synchrone A[64][32] et B[32][32], avec remplissage par zéro des éléments hors limites et synchronisation avant le calcul puis avant le rechargement.",
    "Conserver un bloc de 32x8 threads, threadIdx.x sur les colonnes contiguës et huit accumulateurs FP32 par thread pour les lignes de sortie.",
    "Parcourir K par blocs de 32 au lieu de 16; accumuler les produits en ordre croissant de K et appliquer alpha et beta une seule fois à chaque élément valide de C, sans allocation supplémentaire."
  ]
}
```

### Essai 7 · T2 · 14f2f4326e124c07

Parent : `7b87d96031c1a558c1facf176fc3f388a457162a`. Statut mesuré : **valid**.

Hypothèse déclarée : Le candidat T2 mesuré f069e2e5 établit un contrôle SIMT coalescé 32×32 correct à 0,017417722 s de moyenne. Cette proposition répare l’enum CUDA qui a bloqué la précédente compilation et compare ce contrôle à un chargement TMA mono-étape, sans changer mapping, tuiles ni calcul. TMA n’est utilisé que sur une cible CC ≥ 9, des dimensions multiples de 32 et des pointeurs alignés à 16 octets; les autres tailles passent par le kernel synchrone, ce qui évite les transferts de bord hors limites. L’effet sur le temps reste à mesurer.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Répare le nom de l’enum float OOB utilisé pour l’encodage du descripteur TMA.",
    "Ajoute une variante TMA mono-étape avec le même tile 32×32, mapping de sortie et accumulation FP32 que le contrôle synchrone.",
    "Réserve TMA aux dimensions multiples de 32 et aux pointeurs alignés à 16 octets; les autres formes restent sur le kernel synchrone.",
    "Conserve alpha/beta, les bords arbitraires via le repli synchrone, et aucune allocation supplémentaire."
  ]
}
```

### Essai 8 · T1 · 183d1640ebcb41df

Parent : `91f0b6f6356d29d698a0922a683180b5858b3893`. Statut mesuré : **valid**.

Hypothèse déclarée : Le meilleur candidat mesuré utilise des tuiles de sortie 64x32x32 avec huit accumulateurs par thread. En doublant seulement la hauteur de tuile M à 128, on double la réutilisation de chaque valeur B entre lignes et réduit le nombre de blocs, tout en conservant K=32, les lanes sur les colonnes, les synchronisations et l’ordre d’accumulation FP32. Les 16 accumulateurs par thread et les 20 KiB de mémoire partagée peuvent toutefois pénaliser l’occupation; le bilan de performance reste à mesurer.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Doubler TILE_M de 64 à 128 en gardant TILE_N=32, TILE_K=32 et un bloc 32x8.",
    "Utiliser 16 accumulateurs FP32 par thread; chaque thread calcule 16 lignes espacées de THREADS_Y et conserve son lane sur une colonne contiguë.",
    "Conserver les chargements de tuiles A/B en mémoire partagée, le remplissage zéro des bords, les synchronisations et l’accumulation K croissante.",
    "Appliquer alpha et beta une fois par sortie valide, écrire toutes les sorties et ne pas ajouter d’allocation."
  ]
}
```

### Essai 9 · T1 · 5a1dd9c855e94843

Parent : `cd122f6018c6f6f67d3ab69590c63f143a031ef9`. Statut mesuré : **valid**.

Hypothèse déclarée : Les variantes mesurées montrent que le tuilage 128x32x32 avec 16 accumulateurs par thread est le plus rapide observé (0,007419 s), tandis que le 64x32x32 avec 8 accumulateurs est à 0,007711 s. Ce candidat teste une tuile de sortie 64x64x32 avec 16 accumulateurs par thread (8 lignes et 2 groupes de colonnes). Pour un travail par bloc comparable au 128x32x32, il échange de la réutilisation B contre davantage de réutilisation A et utilise 16 KiB de mémoire partagée au lieu de 20 KiB. Cela pourrait améliorer l’équilibre, mais le coût des deux groupes de colonnes ou la moindre réutilisation B peut aussi réduire les performances; aucun gain n’est présumé.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer la tuile de sortie 32x32 par 64x64, avec une profondeur K de 32 et un bloc de 32x8 threads.",
    "Charger coopérativement les tuiles A[64][32] et B[32][64] en mémoire partagée avec remplissage par zéro des bords et barrières avant et après chaque étape K.",
    "Chaque thread accumule huit lignes et deux groupes de colonnes en registres, en parcourant K dans l’ordre croissant.",
    "Écrire chaque élément valide de C une seule fois en appliquant alpha et beta une seule fois; n’ajouter aucune allocation."
  ]
}
```

### Essai 10 · T1 · ca8357016cdf403b

Parent : `91f0b6f6356d29d698a0922a683180b5858b3893`. Statut mesuré : **valid**.

Hypothèse déclarée : Le parent mesuré 64x32x32 est correct (0,007711 s); les résultats observés incluent aussi 64x64x32 à 0,006471 s et 128x32x32 à 0,007419 s. Ce candidat inverse l’aspect de la tuile, en passant à 32x64x32, tout en gardant K=32, 256 threads, huit sorties par thread, 2048 sorties par bloc et 12 KiB de mémoire partagée. Il échange de la réutilisation B contre de la réutilisation A; pour des matrices carrées divisibles par les tuiles, le nombre total nominal d’éléments chargés de A et B reste équilibré comme dans le parent. L’expérience teste donc l’effet de cet échange de réutilisation et de la géométrie des tuiles, sans présumer d’un gain.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Inverser la forme de la tuile de sortie de 64x32 à 32x64, en gardant TILE_K=32 et le bloc 32x8.",
    "Chaque thread calcule quatre lignes et deux groupes de colonnes avec huit accumulateurs FP32 en registres; les lanes restent contiguës sur les colonnes de chaque groupe.",
    "Charger en mémoire partagée les tuiles A[32][32] et B[32][64], avec remplissage par zéro des bords et synchronisations avant et après l’accumulation K croissante.",
    "Appliquer alpha et beta une seule fois à chaque élément valide de C, sans ajout d’allocation."
  ]
}
```

### Essai 11 · T1 · 5af0d39a8d7b47bb

Parent : `7b87d96031c1a558c1facf176fc3f388a457162a`. Statut mesuré : **valid**.

Hypothèse déclarée : Cette expérience isole le mapping des lanes avant d’explorer davantage la réutilisation : attribuer les colonnes row-major contiguës aux lanes d’un warp devrait rendre les accès à B et C contigus, même sans mémoire partagée. Le calcul reste un produit direct avec accumulation FP32 séquentielle; le gain éventuel par rapport au kernel naïf ou aux variantes tuilées reste à mesurer.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer le mapping où les lanes parcourent les lignes par un bloc 32x8 où les lanes d’un warp parcourent des colonnes row-major contiguës.",
    "Calculer directement une sortie par thread sans mémoire partagée; conserver la boucle K croissante et un accumulateur FP32.",
    "Appliquer alpha et beta une fois par sortie, vérifier les bords avant de lire ou d’écrire C, et n’ajouter aucune allocation."
  ]
}
```

### Essai 12 · T2 · 86d5e6d40a8149a3

Parent : `7b87d96031c1a558c1facf176fc3f388a457162a`. Statut mesuré : **valid**.

Hypothèse déclarée : Le pipeline TMA à deux buffers peut recouvrir le chargement du panneau K suivant avec le calcul courant. Le diagnostic incorrect observé à 512 pourrait venir d’une réutilisation du buffer avant que tous les threads du bloc aient fini de le lire. Ajouter une synchronisation de bloc après l’attente du chargement préfetché teste cette hypothèse sans changer le mapping, les tuiles ni le calcul. Le contrôle SIMT a une moyenne de 0,017417722 s et le TMA mono-étape de 0,015454465 s sur le protocole global; le gain du pipeline reste à mesurer.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Conserve le contrôle SIMT tuilé 32×32, le panneau K de 32 et le calcul FP32 avec alpha/beta.",
    "Conserve deux buffers partagés alignés et les chargements TMA préfetchés avec les mêmes tensor maps.",
    "Ajoute __syncthreads après calcul et attente du préchargement pour empêcher le bloc de réutiliser un buffer avant que tous ses threads aient terminé de le lire.",
    "Conserve le repli SIMT pour bords, incompatibilité d’alignement, absence de matériel CC >= 9 ou indisponibilité de l’encodeur; aucune allocation supplémentaire."
  ]
}
```

### Essai 13 · T1 · 78ad9dfc98a949df

Parent : `82cfa263268f96ba14f36cd66469811f8f87e025`. Statut mesuré : **valid**.

Hypothèse déclarée : Le parent sélectionné est le kernel direct coalescé, correct à 0,0234002 s en moyenne (0,0233961, 0,0234007, 0,0234038 s). Une variante mesurée 64x64x32 est également correcte et atteint 0,0064707 s (0,0064201, 0,0064899, 0,0065022 s). Ce candidat conserve le mapping, la tuile de sortie 64x64 et les 16 accumulateurs FP32 par thread de cette variante, mais double uniquement TILE_K de 32 à 64. Moins d’étapes et de barrières pourraient réduire le surcoût de synchronisation; les 32 KiB de mémoire partagée par bloc, contre 16 KiB, pourraient toutefois limiter l’occupation. Le gain éventuel reste à mesurer.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer le calcul direct par des tuiles de sortie 64x64 et une profondeur de réduction TILE_K=64, avec un bloc 32x8.",
    "Charger coopérativement A[64][64] et B[64][64] en mémoire partagée, remplir de zéros les éléments hors limites et synchroniser avant et après chaque étape K.",
    "Chaque thread accumule huit lignes et deux colonnes dans des accumulateurs FP32, en parcourant K dans l’ordre croissant et en réutilisant les valeurs B entre lignes.",
    "Écrire uniquement les sorties valides, appliquer alpha et beta une fois par sortie, et ne pas ajouter d’allocation."
  ]
}
```

### Essai 14 · T1 · 7868e8c5898c435e

Parent : `7b87d96031c1a558c1facf176fc3f388a457162a`. Statut mesuré : **valid**.

Hypothèse déclarée : À TILE_K=32 et mapping contigu des colonnes aux lanes constants, augmenter la tuile de sortie de 64×64 à 128×64 devrait accroître la réutilisation de B et réduire le nombre de blocs. Cela porte toutefois les accumulateurs de 16 à 32 par thread, ce qui peut augmenter la pression sur les registres et annuler le gain. L’effet reste à mesurer sur 4096 et sur les autres tailles.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer le calcul direct par des tuiles de sortie 128×64 et une profondeur K de 32, avec un bloc de 32×8 threads.",
    "Charger coopérativement les tuiles A[128][32] et B[32][64] en mémoire partagée, avec mise à zéro des éléments hors limites et synchronisations avant et après chaque étape K.",
    "Chaque thread accumule 16 lignes et deux groupes de colonnes en registres, en parcourant K dans l’ordre croissant.",
    "Écrire seulement les sorties valides et appliquer alpha et beta une seule fois par élément de C, sans ajouter d’allocation."
  ]
}
```

### Essai 15 · G · ab3d43a2d9d74803

Parent : `333cfd136707d8ec68b4f134f90a5a24f6b2be25`. Statut mesuré : **valid**.

Hypothèse déclarée : À mapping et tuiles de sortie identiques, augmenter TILE_K de 64 à 96 réduit le nombre d’étapes K et de synchronisations pour 4096. Cela consomme toutefois 48 KiB de mémoire partagée par bloc au lieu de 32 KiB; l’impact sur l’occupation et le temps net reste à mesurer.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Conserver le kernel SIMT FP32 64x64 mesuré et correct, avec son mapping, ses accumulateurs, ses chargements en mémoire partagée, son traitement des bords et son épilogue.",
    "Changer uniquement la profondeur TILE_K de 64 à 96 et renommer le kernel pour refléter ce paramètre; aucune allocation ni précision réduite n’est ajoutée."
  ]
}
```

## softmax — job 781180

Campagne `softmax`. Pipeline achevé : **True**. Essais : 3. Commit retenu : `4cd8282d9f32637ec22ad20f64c9dd360a599b31`. Commit G : `4cd8282d9f32637ec22ad20f64c9dd360a599b31`. G confirmé : True.

Objectif naïf de recherche : 0,000211770 s ; retenu : 0,000041712 s ; G : 0,000041712 s.

Début UTC : 2026-10-23T17:21:52.739802+00:00 ; durée murale : 1476,3 s ; dépassement cible déclaré : 0,0 s.

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | 80c473c2729944fe | valid | 0,000042357 | 8e241367b487bc1d5c05b9c2c1af0c12fe49a60a |
| 2 | T2 | 704724827ba943a4 | valid | 0,000041451 | ced0912660a99537cd3c149af6eb8a2b66b8aa6e |
| 3 | G | e3568bf9b9da4dff | valid | 0,000041685 | 4cd8282d9f32637ec22ad20f64c9dd360a599b31 |

### Essai 1 · T1 · 80c473c2729944fe

Parent : `92a2fb1870d1adbf9762aa674e79da4efe934e08`. Statut mesuré : **valid**.

Hypothèse déclarée : A single CTA per row can replace the baseline's multiple full-matrix operations and intermediate tensors with one fused pass. Masked power-of-two reductions preserve arbitrary column tails; using four warps for narrower rows and eight for wider rows may balance reduction parallelism and CTA resource use, but the controller must measure the effect.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.py"
  ],
  "retained": [
    "Fuse row maximum, exponentiation, sum reduction, and normalization into one Triton kernel with one CTA per row.",
    "Use masked power-of-two column reductions and input strides to support tails and non-contiguous inputs.",
    "Select four warps for blocks up to 2048 columns and eight warps for wider blocks."
  ]
}
```

### Essai 2 · T2 · 704724827ba943a4

Parent : `92a2fb1870d1adbf9762aa674e79da4efe934e08`. Statut mesuré : **valid**.

Hypothèse déclarée : A fused Triton CTA can compute each row's maximum, exponentials, sum, and normalization without materializing intermediate matrices, potentially reducing launch and memory traffic relative to the correct PyTorch baseline (mean 0.0002116427 s). Grouping four rows for narrow columns and fewer rows as widths grow may amortize scheduling while limiting per-CTA work and allowing more warp cooperation for wider reductions. This is a throughput hypothesis, not a measured speedup.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.py"
  ],
  "retained": [
    "Replaced the sequence of PyTorch reductions and elementwise operations with one fused Triton kernel for row maximum, exponentiation, row sum, and normalization.",
    "Used a two-dimensional CTA tile with masked row and column tails. The row group is selected by width (4 rows through 128 columns, 2 through 1024, otherwise 1), with four warps per CTA.",
    "Passed input strides directly for 2D inputs; for higher-rank tensors, made dimension 1 the contiguous reduction axis and restored the original axis order in the fresh output."
  ]
}
```

### Essai 3 · G · e3568bf9b9da4dff

Parent : `ced0912660a99537cd3c149af6eb8a2b66b8aa6e`. Statut mesuré : **valid**.

Hypothèse déclarée : Adapting T2's measured fused grouped-row softmax to the guaranteed contiguous 2D matrix input removes unused stride and dimension-reordering paths and may trim host-launch setup while retaining stable FP32 reductions and masked tails. The adaptation's performance has not been measured.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.py"
  ],
  "retained": [
    "Retained T2's fused FP32 row-maximum, exponentiation, sum, and normalization kernel with masked power-of-two column tiles.",
    "Retained T2's row grouping by column width and four-warps-per-CTA launch configuration.",
    "Simplified the host path to the specified contiguous 2D input and allocated a fresh same-shape output."
  ]
}
```

## stencil3d — job 781174

Campagne `stencil3d`. Pipeline achevé : **True**. Essais : 4. Commit retenu : `589fb88b8ecb46d37e9f73624a3a48fd3b2be89b`. Commit G : `589fb88b8ecb46d37e9f73624a3a48fd3b2be89b`. G confirmé : True.

Objectif naïf de recherche : 0,467602236 s ; retenu : 0,053106799 s ; G : 0,053106799 s.

Début UTC : 2026-10-23T17:14:55.642445+00:00 ; durée murale : 1676,6 s ; dépassement cible déclaré : 0,0 s.

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | b47bb656019f4161 | valid | 0,239583596 | 614bf3708f580c926070283e5af6f2206b632bdb |
| 2 | T2 | 6403fa30c9064baa | valid | 0,079834289 | 0e3c21e60511f7c6ecb50c0074fc5cf6a1e37e2f |
| 3 | T3 | e351d35acfdf4f38 | valid | 0,480669222 | ddd8dfe2e4e58b2b892638ad03e83b3ebedd1f34 |
| 4 | G | 862672b1dd434e1e | valid | 0,052896636 | 589fb88b8ecb46d37e9f73624a3a48fd3b2be89b |

### Essai 1 · T1 · b47bb656019f4161

Parent : `10c52421c7918e55390cfb55f4b0e4dbb50d6ad4`. Statut mesuré : **valid**.

Hypothèse déclarée : Cette branche combine une seule équipe OpenMP conservée pour les six pas et un ordonnancement statique aplati sur les itérations z/y. Elle supprime les ouvertures répétées de régions parallèles; la barrière implicite de chaque omp for conserve la dépendance entre pas. La répartition statique des lignes z/y pourrait mieux équilibrer le travail tout en gardant x contigu. Cette branche seule ne permet pas d’attribuer séparément un effet à chacun des deux facteurs; il faut comparer des variantes appariées avant de conclure.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Conserver une équipe OpenMP pendant les six pas avec num_threads dérivé de threads.",
    "Répartir statiquement les plans z/y avec collapse(2), en gardant x comme boucle interne.",
    "Garder la même expression arithmétique, la parité des buffers et la barrière implicite entre pas; ne pas ajouter de tuilage temporel."
  ]
}
```

### Essai 2 · T2 · 6403fa30c9064baa

Parent : `10c52421c7918e55390cfb55f4b0e4dbb50d6ad4`. Statut mesuré : **valid**.

Hypothèse déclarée : Hoisting each row base and the four coefficients, then expressing the radius-three neighborhood with constant pointer offsets under an OpenMP SIMD directive on contiguous x iterations, may reduce index/coeff overhead and expose vectorization. The stencil domain, arithmetic grouping, thread partition and timestep loop remain unchanged; official measurements must establish any benefit.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Compute the z/y row base once and use constant neighbor offsets from the contiguous x position.",
    "Hoist coefficients into scalar locals and add an OpenMP SIMD directive to the x loop only, preserving the original stencil grouping and timestep/thread structure."
  ]
}
```

### Essai 3 · T3 · e351d35acfdf4f38

Parent : `10c52421c7918e55390cfb55f4b0e4dbb50d6ad4`. Statut mesuré : **valid**.

Hypothèse déclarée : Éviter la copie complète de input1 et la mise à zéro complète du second tampon devrait réduire le trafic mémoire : seul le complément de [4,n-4)^3 est initialisé, tandis que chaque cellule intérieure est écrite par les étapes qui la produisent. La validité et l’effet sur le temps restent à mesurer.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Initialiser uniquement le complément de [4,n-4)^3 dans les deux tampons, avec un repli à l’initialisation complète lorsque n <= 8.",
    "Lire input1 directement au premier pas et utiliser input1 comme terme temporel précédent au deuxième pas; les pas suivants conservent la récurrence sur les tampons."
  ]
}
```

### Essai 4 · G · 862672b1dd434e1e

Parent : `0e3c21e60511f7c6ecb50c0074fc5cf6a1e37e2f`. Statut mesuré : **valid**.

Hypothèse déclarée : Combiner le noyau SIMD T2, mesuré valide à 0,07983 s, au découpage OpenMP statique z/y de T1, mesuré valide à 0,23958 s, pourrait améliorer le temps sur un ou quatre threads. Les transformations occupent des niveaux de boucle distincts; l’interaction et tout gain restent à mesurer.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Conserver le calcul du row base, les coefficients hoistés, les offsets constants et la directive omp simd sur x de T2, sans modifier le groupement arithmétique.",
    "Ajouter de T1 une équipe OpenMP persistante num_threads(threads) et un omp for collapse(2) schedule(static) sur z/y; garder la synchronisation implicite à chaque pas.",
    "Préserver les six étapes, les buffers pairs/impairs et leur initialisation complète."
  ]
}
```

## stencil_y — job 781116

Campagne `stencil_y`. Pipeline achevé : **False**. Essais : 23. Commit retenu : `6e67b2e7565d8fe16129bac260683b0f124ef141`. Commit G : `6e67b2e7565d8fe16129bac260683b0f124ef141`. G confirmé : True.

Objectif naïf de recherche : 0,000003429 s ; retenu : 0,000003272 s ; G : 0,000003272 s.

Erreur de pipeline : ForestError: Submission requires a Makefile and run.sh in the imported repository

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | e8f2b48b286947ba | valid | 0,000003608 | 136a088fda446a10917f5d00667f41383404af42 |
| 2 | T2 | 7e8d9154817c4a9c | valid | 0,000003354 | cf4d5fc609314cc34f0686a628181f84f8b03ab6 |
| 3 | T3 | f4f33edf026d472a | valid | 0,000003434 | 9efa7c9b4701f1b2ca107ed696bfe8dd63d17f64 |
| 4 | T3 | 0b2d1304baba411e | valid | 0,000003456 | d94963c2148e7313f482bb579e3a4260ead929db |
| 5 | T3 | c5b64478d9af4d01 | valid | 0,000003417 | 332beec2b59cdad44725e979cd4eced07a3309f0 |
| 6 | T1 | 126467170e624117 | incorrect | NR | 5726ff2cb02d1354eefd5e0bede9b4b4955ee8cc |
| 7 | T2 | 1ef80cca16fa4bb3 | valid | 0,000003747 | a8a51dd6406c72faef0fd6c7c19e28e44793c449 |
| 8 | T3 | 7e04c7b16dcd4748 | valid | 0,000003453 | dbe492ca2462241d6a2d4d18cc45334f49a28216 |
| 9 | T2 | f56ead9eed404ac7 | valid | 0,000003956 | a42a48cd6de2febba89ba0dc043f511b1791132a |
| 10 | T3 | 50070f42244745db | valid | 0,000003409 | 0fddd949d73bf1c64a91f3a9a3b2799781fc6e83 |
| 11 | T2 | ba57640319fa422e | valid | 0,000004008 | 39a981c168acc491439edd0f1d30f58d38efd794 |
| 12 | T3 | 4d3f820fb7bb4916 | valid | 0,000003383 | 65db63dbc31d9d1e6756fce6fc917999f6de1d1a |
| 13 | T2 | 4d4a776e96434e71 | valid | 0,000003269 | 8da16d8665ae51af77a46ffbfaf880f7cf03d069 |
| 14 | T1 | c364a9fae46547c2 | valid | 0,000003697 | 86cde4f2dc50875f365b4a0b8d279883ecfc5778 |
| 15 | T3 | 1664dc23b93d4323 | valid | 0,000003400 | feb5df92f2f65ae586928b7a98a9deb8dd29b434 |
| 16 | T2 | 2bdfb0b9604b4692 | valid | 0,000003258 | ba1974d70b628b6dbde402eba7ecd233034040d0 |
| 17 | T1 | 5578690d1f284142 | incorrect | NR | dcdaa79db8bcbd0056f5cdaab738fdfe93e76506 |
| 18 | T3 | ebdc42c580e246a9 | valid | 0,000003467 | de17bbf1badece4b078a44dc604487378b4f1ced |
| 19 | T2 | d18ed8872c304525 | valid | 0,000003830 | 7589482f50160c52377c0aae2e0c3b7ccefadf06 |
| 20 | T2 | 66687fa21161480a | valid | 0,000003583 | 53d7586ccaf59a3376f690a15384ad939b0dbe5b |
| 21 | T3 | b1fbb70f28d54780 | valid | 0,000003427 | 65d2b7e836c92f9b84420b51d8eb0bd7c4d1a6e4 |
| 22 | T2 | 408affd6deb247aa | valid | 0,000003494 | 2295a0848c2af7dacee16c5955bac496846cc1b3 |
| 23 | G | e6d8b8c0158f4387 | valid | 0,000003324 | 6e67b2e7565d8fe16129bac260683b0f124ef141 |

### Essai 1 · T1 · e8f2b48b286947ba

Parent : `341c1e26a43209b7311133061de93463c6073591`. Statut mesuré : **valid**.

Hypothèse déclarée : A direct-global kernel may reduce complete-run latency by removing shared-memory staging and barriers, while keeping global loads coalesced because each warp covers contiguous x positions. Eight direct neighbor loads may offset those savings; measurement is needed to determine the tradeoff.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Replace shared-memory y-tile staging and barriers with eight direct global neighbor loads per output.",
    "Map each warp's 32 lanes to consecutive x coordinates using a 32-by-8 thread block.",
    "Apply the y-derivative coefficients scaled by m-1 and wrap neighbor coordinates at both period endpoints; handle dimensions smaller than the stencil period."
  ]
}
```

### Essai 2 · T2 · 7e8d9154817c4a9c

Parent : `341c1e26a43209b7311133061de93463c6073591`. Statut mesuré : **valid**.

Hypothèse déclarée : The measured baseline is correct but its derivative-y block places only four x coordinates in each contiguous warp segment. A 32x32 output tile, staged as 40x32 shared rows for the ±4 halo and mapped to 32x8 threads, should improve x coalescing, reduce the 64-cubed CTA count from 1024 to 256, and amortize the single staging barrier across four outputs per thread. It adds halo loads (40 rows per 32 output rows), so the complete-run measurement must determine whether the improved access pattern and lower CTA count outweigh that cost.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Replace the four-x full-y pencil with a 32x32 output tile, cooperatively staging 40 y rows including the four-row halos.",
    "Use a 32x8 block so each warp accesses 32 contiguous x values and each thread computes four y outputs from shared memory, with one barrier after cooperative loading.",
    "Use ceil-divided runtime grids, guard partial edge tiles, and wrap only out-of-range y indices by m-1 while retaining the endpoint row; pass the corresponding y-derivative coefficients to the kernel."
  ]
}
```

### Essai 3 · T3 · f4f33edf026d472a

Parent : `341c1e26a43209b7311133061de93463c6073591`. Statut mesuré : **valid**.

Hypothèse déclarée : Specializing the fixed y coefficients as compile-time FP32 expressions may remove per-thread constant-memory coefficient reads. Explicit forward FMA accumulation may reduce separate arithmetic instructions while keeping the existing one-launch mapping and shared-memory dataflow. This is a testable latency hypothesis, not a claimed speedup.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Specialized the four fixed y coefficients inside the kernel using the baseline FP32 coefficient expressions for dimension 64.",
    "Rewrote the left-to-right sum as one initial product followed by three explicit forward fmaf accumulations.",
    "Preserved the existing launch geometry, shared-memory staging, barriers, neighbors, endpoint handling, buffers, and output assignment."
  ]
}
```

### Essai 4 · T3 · 0b2d1304baba411e

Parent : `341c1e26a43209b7311133061de93463c6073591`. Statut mesuré : **valid**.

Hypothèse déclarée : Specializing the four fixed y coefficients while accumulating two independent coefficient-term pairs may shorten the serial FP32 dependency chain compared with the prior forward FMA chain. The pairwise form adds a final sum and may not reduce full-run latency; correctness and performance, especially near cancellation, require measurement.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Specialized only the y coefficients using the baseline FP32 expressions for the fixed y dimension.",
    "Replaced the forward serial FMA accumulation with two pairwise FMA accumulations followed by a final sum, testing a shorter dependency chain against the extra operation.",
    "Preserved all neighbors, endpoint handling, shared-memory staging, launch configuration, buffers, and output coverage."
  ]
}
```

### Essai 5 · T3 · c5b64478d9af4d01

Parent : `9efa7c9b4701f1b2ca107ed696bfe8dd63d17f64`. Statut mesuré : **valid**.

Hypothèse déclarée : The two valid arithmetic variants have similar measured means: the forward FMA form is 3.4341 µs and the two-pair FMA form is 3.4560 µs, versus 3.5629 µs for baseline. This contrasting candidate tests whether four independently rounded FP32 products followed by a balanced addition tree expose enough instruction-level parallelism to offset extra operations and altered rounding. Cancellation-sensitive tolerance and full-run latency must be measured; no speedup is assumed.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Retained the four fixed y coefficients specialized using the existing my=64 FP32 expressions.",
    "Replaced the serial forward FMA accumulation with four explicitly rounded FP32 products and a balanced tree of explicitly rounded additions to test independent arithmetic issue against the FMA forms.",
    "Preserved the original neighbors, endpoint handling, shared-memory dataflow, launch mapping, buffers, and output coverage."
  ]
}
```

### Essai 6 · T1 · 126467170e624117

Parent : `341c1e26a43209b7311133061de93463c6073591`. Statut mesuré : **incorrect**.

Hypothèse déclarée : The direct-global kernel's existing 32-by-4 block creates many small CTAs. Raising its y extent to 16 retains contiguous x lanes and one output per thread while reducing CTA count fourfold for the fixed 64-cubed workload; the larger CTA could instead reduce latency hiding or occupancy. Compare complete-run latency and correctness without changing the stencil or wrapping.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Increase the block y extent from 4 to 16 while retaining 32 contiguous x lanes and one output per thread.",
    "Update the y-grid ceiling calculation to cover all rows for arbitrary positive m.",
    "Keep the single-launch eight-neighbor direct-global stencil, period wrapping, coefficients, host contract, and edge handling unchanged."
  ]
}
```

Diagnostic : Protected correctness checks failed

### Essai 7 · T2 · 1ef80cca16fa4bb3

Parent : `cf4d5fc609314cc34f0686a628181f84f8b03ab6`. Statut mesuré : **valid**.

Hypothèse déclarée : Extending the y tile from 32 to 64 outputs while keeping x-contiguous warps and a 32x8 block should reduce the y-tile CTA count and improve halo reuse (72 staged rows for 64 outputs versus 40 for 32). The tradeoff is eight outputs per thread, 9 KiB of shared memory per CTA, and fewer CTAs, which could increase register pressure or reduce parallelism on the supplied GH200/CUDA 12.6.3 target. Measure the complete run against the correct 32x32 parent; no speedup is assumed.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Increase the shared-memory y tile from 32 to 64 output rows, staging 72 rows to include the four-row halo on each side.",
    "Keep a 32x8 block so each warp loads contiguous x values; each thread computes up to eight output rows after one synchronization barrier.",
    "Use runtime ceil-divided tile grids and guarded writes, preserving the period-(m-1) y-index mapping and endpoint behavior."
  ]
}
```

### Essai 8 · T3 · 7e04c7b16dcd4748

Parent : `341c1e26a43209b7311133061de93463c6073591`. Statut mesuré : **valid**.

Hypothèse déclarée : A reverse-order serial FMA chain evaluates the fixed coefficient terms from smallest to largest magnitude, while retaining the same number of arithmetic steps as the forward FMA form. This tests whether term order affects cancellation tolerance or full-run latency relative to the previously measured forward, pairwise, and balanced-product forms; the close prior means do not establish a speedup or its cause.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Specialized the four fixed y coefficients in the kernel using the baseline FP32 expressions for dimension 64.",
    "Reordered the accumulation from smallest- to largest-magnitude coefficient: one initial product followed by three explicit fmaf operations.",
    "Left the stencil neighbors, endpoint handling, shared-memory dataflow, launch geometry, buffers, and output coverage unchanged."
  ]
}
```

### Essai 9 · T2 · f56ead9eed404ac7

Parent : `341c1e26a43209b7311133061de93463c6073591`. Statut mesuré : **valid**.

Hypothèse déclarée : The correct 32×32 shared tile measured 3.354 μs, faster than the 3.563 μs baseline, while the 32×64 tile measured 3.747 μs despite staging fewer halo rows per output. Test a contrasting 16-row tile with a 32×4 block: it halves per-CTA shared storage and thread count while retaining four outputs per thread and x-contiguous warp loads. This may improve occupancy, but doubles the CTA count and increases staged rows per output (1.5 versus 1.25 for the 32-row tile), so no speedup is assumed.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Replace the original pencil kernel with a single-launch 16-output-row y tile, staging 24 rows including four halo rows on each side.",
    "Use a 32×4 block: contiguous x loads per warp, cooperative shared-memory staging, one barrier, and four y outputs per thread.",
    "Compute y coefficients from runtime m; use ceil-divided x/y grids, guard partial tiles, preserve endpoint-aware period-(m−1) wrapping, and write all in-range outputs."
  ]
}
```

### Essai 10 · T3 · 50070f42244745db

Parent : `341c1e26a43209b7311133061de93463c6073591`. Statut mesuré : **valid**.

Hypothèse déclarée : Specializing the four y coefficients with the same FP32 expressions and grouping the positive-coefficient terms (ay, cy) and negative-coefficient terms (by, dy) into two independent FMA chains may change instruction scheduling and cancellation behavior relative to the prior accumulation forms. The prior valid means are close (3.4175–3.4560 µs), so this tests a distinct grouping without assuming a speedup; varied signed/cancellation inputs and full-run latency must be measured.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Specialized the four fixed y coefficients in the kernel using constexpr FP32 expressions corresponding to the existing dimension-64 coefficient formulas.",
    "Formed two explicit FMA chains grouped by coefficient sign: ay with cy, and by with dy; combined their results in a final FP32 addition.",
    "Preserved neighbor accesses, endpoint handling, shared-memory dataflow, launch mapping, buffers, and output coverage."
  ]
}
```

### Essai 11 · T2 · ba57640319fa422e

Parent : `a8a51dd6406c72faef0fd6c7c19e28e44793c449`. Statut mesuré : **valid**.

Hypothèse déclarée : The 32x32 shared tile with a 32x8 block measured 3.354 μs, while the 32x64 parent measured 3.747 μs and the 16-row/32x4 candidate measured 3.956 μs. Test the same 32-row tile with only four y lanes: each 128-thread CTA stages the same 40x32 halo tile and computes eight outputs per thread. This could reduce per-CTA thread scheduling cost or improve residency, but doubles each thread's staging work relative to 32x8 and may raise register pressure; compare full-run latency and correctness without presuming a gain.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Replace the parent 64-output-row tile with a 32-output-row tile and stage its four-row halos on both sides in a 40x32 shared array.",
    "Map the block to 32x4 threads: each warp loads contiguous x values, four y lanes cooperatively load the tile, and each thread computes eight y outputs after one barrier.",
    "Use runtime ceil-divided x/y grids and guarded writes; wrap only y indices outside [0,m) by period m-1 (or 1 when m=1), leaving endpoint m-1 unmapped."
  ]
}
```

### Essai 12 · T3 · 4d3f820fb7bb4916

Parent : `341c1e26a43209b7311133061de93463c6073591`. Statut mesuré : **valid**.

Hypothèse déclarée : Adjacent stencil offsets grouped as (a,b) and (c,d) let two independent FMA accumulations run in parallel. This contrasts with the measured serial, sign-grouped and balanced-product forms; the extra independent products and final addition may or may not offset the shorter dependency chains. The prior close means do not establish a speedup. The controller should check tolerance on varied signed and cancellation inputs and compare full-run latency.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Specialized the four y coefficients in the kernel using the existing FP32 expressions for fixed my=64.",
    "Computed the four shared-memory neighbor differences explicitly, then grouped adjacent offsets into two independent fmaf accumulations: (ay*d1 + by*d2) and (cy*d3 + dy*d4), followed by one addition.",
    "Preserved neighbor access, endpoint wrapping, shared-memory dataflow and synchronization, launch mapping, buffers, and output coverage."
  ]
}
```

### Essai 13 · T2 · 4d4a776e96434e71

Parent : `cf4d5fc609314cc34f0686a628181f84f8b03ab6`. Statut mesuré : **valid**.

Hypothèse déclarée : The correct 32×32/32×8 candidate measured 3.354 μs; the 32×64/32×8 variant measured 3.747 μs, while the 16×32/32×4 variant measured 3.956 μs but changed both tile height and block mapping. This trial isolates tile height while retaining the 32×8 block: a 16×32 output tile stages 24×32 values, halves shared storage per CTA, and gives each thread two outputs rather than four. It also doubles the y CTA count and raises staged rows per output from 1.25 to 1.5, so test whether the smaller tile offsets those costs without assuming a speedup.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Reduce the output tile height from 32 to 16 while keeping the x tile at 32 and staging four halo rows at each end in shared memory (24×32 floats).",
    "Retain a 32×8 block so each warp accesses contiguous x positions; cooperatively load three tile rows per thread, synchronize once, and compute two output rows per thread.",
    "Use a runtime ceil-divided y grid and guard output writes; retain the endpoint-aware period-(m−1) wrapping for out-of-range y samples and compute every in-range output."
  ]
}
```

### Essai 14 · T1 · c364a9fae46547c2

Parent : `136a088fda446a10917f5d00667f41383404af42`. Statut mesuré : **valid**.

Hypothèse déclarée : The correct 32-by-8 direct-global parent averaged 3.608 µs, slightly slower than the 3.563 µs baseline. Test a 32-by-4 block while retaining the same stencil and x-contiguous warp mapping: fewer warps per CTA may improve scheduling or occupancy, while doubling CTA count may instead add overhead. The prior 32-by-16 attempt failed correctness, so it provides no usable timing comparison; this experiment leaves indexing and wrapping unchanged.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Change the block from 32-by-8 to 32-by-4 threads while preserving contiguous x lanes and one output per thread.",
    "Adjust the y-grid ceiling to cover all rows for the 4-thread block height; retain the direct eight-neighbor global loads, coefficients, wrapping, and single-kernel launch."
  ]
}
```

### Essai 15 · T3 · 1664dc23b93d4323

Parent : `341c1e26a43209b7311133061de93463c6073591`. Statut mesuré : **valid**.

Hypothèse déclarée : Pairing the largest and smallest-magnitude y terms (ay·d1 with dy·d4), and the two middle terms (by·d2 with cy·d3), gives two independent fused accumulations with a final addition. This contrasts with the previously measured adjacent-offset and same-sign groupings while preserving the specified FP32 coefficient expressions and stencil dataflow. Prior arithmetic candidates were all correct, with means clustered at 3.3826–3.4560 µs versus the 3.5629 µs baseline; that spread does not establish a repeatable benefit. Measure tolerance on signed and cancellation inputs and compare full-run latency without assuming this pairing is faster.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Specialized the four fixed y coefficients inside derivative_y using the same FP32 expressions as setDerivativeParameters() for my=64.",
    "Computed the four shared-memory neighbor differences unchanged, then evaluated two independent FMA pairs: ay·d1 + dy·d4 and by·d2 + cy·d3, followed by one FP32 addition.",
    "Left neighbor selection, endpoint handling, shared-memory dataflow and barriers, launch mapping, buffers, and output coverage unchanged."
  ]
}
```

### Essai 16 · T2 · 2bdfb0b9604b4692

Parent : `cf4d5fc609314cc34f0686a628181f84f8b03ab6`. Statut mesuré : **valid**.

Hypothèse déclarée : Test a contrasting block mapping while keeping the 32×32 output tile, shared tile, launch grid, and single barrier unchanged. A 32×16 block doubles the threads participating per tile and reduces each thread from four to two output rows, which may distribute staging and arithmetic more effectively; the 512-thread block may instead increase scheduling or occupancy costs. Compare full-run latency and oracle correctness without assuming a gain.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Keep the 32×32 output tile and cooperative 40×32 shared-memory tile, including four-row halos and the endpoint-aware period-(m−1) mapping.",
    "Change the block from 32×8 to 32×16; distribute staged rows with stride 16 and compute two output rows per thread while retaining contiguous x lanes and one barrier.",
    "Keep the runtime ceil-divided grid, output guards, and host entry point unchanged."
  ]
}
```

### Essai 17 · T1 · 5578690d1f284142

Parent : `341c1e26a43209b7311133061de93463c6073591`. Statut mesuré : **incorrect**.

Hypothèse déclarée : The current 64-by-4 block creates twice as many y-grid CTAs as a 64-by-8 block. Raising only the block y extent keeps x-contiguous warp lanes and one output per thread, while reducing CTA count for a given domain; test whether that lowers complete-run latency or whether the larger 512-thread CTA reduces scheduling flexibility. Earlier correct direct-global candidates averaged 3.608 µs (32-by-8) and 3.697 µs (32-by-4), both above the 3.563 µs baseline, so no speedup is assumed.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Increase the CUDA block shape from 64-by-4 to 64-by-8 and update the y-grid ceiling accordingly, leaving x-contiguous warp mapping intact.",
    "Retain one output per thread, eight direct global y-neighbor loads, coefficient calculations, period wrapping, and the single kernel launch."
  ]
}
```

Diagnostic : Protected correctness checks failed

### Essai 18 · T3 · ebdc42c580e246a9

Parent : `341c1e26a43209b7311133061de93463c6073591`. Statut mesuré : **valid**.

Hypothèse déclarée : Factoring the specialized FP32 y coefficients into two pairs using compile-time ratios derived from those same coefficients creates independent fused pair calculations before the final scale-and-accumulate. This may shorten the accumulation dependency chain, but it changes rounding and may not improve latency; signed and cancellation inputs must pass tolerance before comparing full-run latency.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Specialized ay, by, cy, and dy within derivative_y using the same FP32 expressions with the y dimension scale.",
    "Derived compile-time coefficient ratios by/ay and dy/cy, fused each ratio-weighted pair of unchanged stencil differences, then scaled and accumulated the pair results.",
    "Left neighbor selection, endpoint handling, shared-memory dataflow and barriers, launch mapping, buffers, and output coverage unchanged."
  ]
}
```

### Essai 19 · T2 · d18ed8872c304525

Parent : `a42a48cd6de2febba89ba0dc043f511b1791132a`. Statut mesuré : **valid**.

Hypothèse déclarée : The 32×32 output tile with a 32×16 block measured 3.258 μs, while the 64×32 tile with a 32×8 block measured 3.747 μs and the selected 16×32/32×4 parent measured 3.956 μs. Test a 64×32 output tile with a 32×16 block: it stages 72 rows for 64 outputs and halves the CTA count versus a 32-row tile, while distributing each thread four outputs rather than eight in the previously tested 64-row/32×8 mapping. This may reduce per-thread work, but the 512-thread CTA could hurt residency; no speedup is assumed.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Increase the y output tile from 16 to 64 rows while retaining a 32-wide x tile and four-row halo on each side, for a 72×32 shared tile.",
    "Use a 32×16 block to keep x-contiguous warp accesses, distribute staging cooperatively, and compute four y outputs per thread after one barrier.",
    "Retain runtime ceil-divided grids, bounds-check partial x/y tiles, and preserve the endpoint-aware period-(ny−1) mapping for out-of-range y samples so every output is written."
  ]
}
```

### Essai 20 · T2 · 66687fa21161480a

Parent : `341c1e26a43209b7311133061de93463c6073591`. Statut mesuré : **valid**.

Hypothèse déclarée : The best recorded 32×32 output tile with a 32×16 block measured 3.258 μs; the 16-row/32-wide variant measured 3.269 μs, while the tested 64-row/32-wide variants measured 3.747–3.830 μs. Since the prior trials varied y height and block mapping but kept x tile width at 32, test a 64-wide-x, 32-high-y tile with a 64×8 block. It retains 32 contiguous x values per warp and four y outputs per thread, while halving the x CTA count for n=64. Its 10 KiB shared tile and reduced CTA count may help scheduling, but the larger tile may instead hurt occupancy or per-thread work; no gain is assumed.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Replace the 32-wide x tile with a 64-wide x tile while retaining a 32-row y output tile; cooperatively stage 40×64 values including four-row y halos using a 64×8 block.",
    "Map each warp to 32 contiguous x values and compute four y outputs per thread; use ceil-divided runtime grids and guard output tails.",
    "Wrap only out-of-range staged y coordinates with period m−1, retain the valid endpoint row m−1, and derive y coefficients from runtime m without persistent coefficient state."
  ]
}
```

### Essai 21 · T3 · b1fbb70f28d54780

Parent : `341c1e26a43209b7311133061de93463c6073591`. Statut mesuré : **valid**.

Hypothèse déclarée : The eight observed arithmetic programs were all distinct and valid, with measured means clustered at 3.3826–3.4673 µs versus the 3.5629 µs baseline; this does not establish a repeatable arithmetic benefit. This candidate tests whether four independent, explicitly rounded FP32 products followed by a balanced pairwise sum can shorten the dependency chain relative to FMA accumulations, despite its greater operation count. The controller should verify tolerance on varied signed and cancellation inputs and measure full-run latency.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Specialized the four y coefficients inside derivative_y using the same FP32 coefficient expressions as the parameter setup for my=64.",
    "Kept all four shared-memory neighbor differences unchanged, then evaluated separately rounded products with __fmul_rn and an explicit balanced pairwise sum using __fadd_rn.",
    "Preserved endpoint handling, shared-memory dataflow and barriers, launch mapping, buffer behavior, and output coverage."
  ]
}
```

### Essai 22 · T2 · 408affd6deb247aa

Parent : `53d7586ccaf59a3376f690a15384ad939b0dbe5b`. Statut mesuré : **valid**.

Hypothèse déclarée : Test a 32-wide, 16-row shared tile with a 32×8 block, where each thread computes two adjacent y outputs. Explicitly keeping their ten distinct stencil samples in registers may reduce shared-memory reads from sixteen per pair of independent outputs to ten. The shorter tile stages 24 rows for 16 outputs (versus 40 for 32 outputs), so it has more tile loads per output and twice as many y CTAs as a 32-row tile. Compare complete-run latency and oracle correctness; no gain is assumed.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Use a 32-wide x tile and 16-row y output tile with a 32×8 block, cooperatively staging 24 rows including four-row halos and synchronizing once.",
    "Assign each thread two adjacent y outputs and explicitly retain their ten distinct shared samples in registers, so the two stencil expressions reuse samples.",
    "Use ceil-divided runtime grids, guard both output writes and x edges, and preserve endpoint-aware wrapping by m−1 for out-of-range y source rows."
  ]
}
```

### Essai 23 · G · e6d8b8c0158f4387

Parent : `ba1974d70b628b6dbde402eba7ecd233034040d0`. Statut mesuré : **valid**.

Hypothèse déclarée : Retaining the measured T2 shared-memory tile and changing only the arithmetic schedule to two independent adjacent-offset FMA pairs may shorten dependencies. The extra products and altered rounding may cancel that benefit; correctness and performance are unmeasured for this combination.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Retained T2's 32×32 output tile, 40×32 shared tile, 32×16 CTA, single shared-memory barrier, endpoint-aware halo wrap, and one-launch structure.",
    "Adapted T3's adjacent-offset arithmetic idea: compute four differences, form two independent fmaf pairs, then add the pair results.",
    "Preserved the host entry point, existing buffer use, and complete output coverage."
  ]
}
```

## sumabs — job 781181

Campagne `sumabs`. Pipeline achevé : **True**. Essais : 4. Commit retenu : `858fba34d62836a6fe907b3d372251f77a6062dd`. Commit G : `858fba34d62836a6fe907b3d372251f77a6062dd`. G confirmé : True.

Objectif naïf de recherche : 0,001227008 s ; retenu : 0,000292585 s ; G : 0,000292585 s.

Début UTC : 2026-10-23T17:22:05.239123+00:00 ; durée murale : 1604,1 s ; dépassement cible déclaré : 0,0 s.

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | b4e8dfcb51e44ba5 | valid | 0,000447283 | b03a75529ea8ebfa47418a809728c9c2d016b50a |
| 2 | T2 | 916159dcefd9460e | valid | 0,000449828 | 73a3b1534976bf86d73e92fd158725d6352dd533 |
| 3 | T2 | c13634967bc74da8 | valid | 0,000453981 | 1b91ff618f44d5fa3edb5d289182c1b423c4dcb3 |
| 4 | G | 40a39b6a5cc443f6 | valid | 0,000292660 | 858fba34d62836a6fe907b3d372251f77a6062dd |

### Essai 1 · T1 · b4e8dfcb51e44ba5

Parent : `ad2fd944207685e96e4b37013540b0ada44b4787`. Statut mesuré : **valid**.

Hypothèse déclarée : The baseline performs two kernels and materializes an n-element absolute-value buffer. A fused kernel can avoid that full-size scratch write/read and one kernel launch by reducing absolute values from x within each block and atomically adding each block total. A size-based grid capped at 1024 blocks uses about 1024 input values per block before the cap, limiting unnecessary blocks for small n while bounding atomics for large n. The required output reset remains included and ordered before the kernel on the default stream; end-to-end measurements will determine whether the saved traffic and launch outweigh atomic contention.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Fused absolute-value calculation, per-thread accumulation, CUB block reduction, and per-block atomic addition into one kernel.",
    "Removed the n-element absolute-value scratch intermediate and its write/read path.",
    "Selected a grid from n at approximately one block per 1024 inputs, capped at 1024 blocks, while retaining the output reset before launch."
  ]
}
```

### Essai 2 · T2 · 916159dcefd9460e

Parent : `ad2fd944207685e96e4b37013540b0ada44b4787`. Statut mesuré : **valid**.

Hypothèse déclarée : The measured baseline is correct and averages 1.227 ms, but writes and rereads n scratch values between kernels. Computing abs and reducing directly from x in each first-stage block should replace that full-size intermediate with at most 4096 partials. A cap of 4096 blocks exposes more input parallelism than the baseline's 1024 blocks for large inputs, while the second launch reduces only those written partials and overwrites output. The two launches are included; speed relative to the atomic alternative and baseline remains to be measured.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Replace the full-length absolute-value scratch pass with direct input abs accumulation and one CUB block-reduced partial per first-stage block.",
    "Cap the first-stage grid at 4096 blocks, with at least one block and generic ceil(n/256) sizing for smaller inputs.",
    "Reduce only the written block partials in a second kernel and overwrite output without atomics or a prior output reset."
  ]
}
```

### Essai 3 · T2 · c13634967bc74da8

Parent : `73a3b1534976bf86d73e92fd158725d6352dd533`. Statut mesuré : **valid**.

Hypothèse déclarée : The selected parent is the only distinct direct two-stage program in the catalog: it is valid, averages 0.4498 ms, and the valid baseline averages 1.2274 ms. Raising the generic first-stage block cap from 4096 to 8192 halves the per-block scan work for sufficiently large inputs, which may improve input throughput; it also doubles the maximum partial count, increasing the second reduction's work. The partial list remains small relative to the input, but whether the tradeoff helps end-to-end time, including both launches, is unmeasured. No atomic-alternative result is available here.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Raise the generic first-stage block cap from 4096 to 8192 while retaining 256-thread blocks and ceil(n/256) sizing for smaller inputs.",
    "Keep writing one partial per launched block and have the unchanged second kernel reduce exactly those written partials and overwrite output."
  ]
}
```

### Essai 4 · G · 40a39b6a5cc443f6

Parent : `b03a75529ea8ebfa47418a809728c9c2d016b50a`. Statut mesuré : **valid**.

Hypothèse déclarée : Four independent per-thread accumulators may expose more memory-level instruction parallelism and shorten the serial accumulation dependency chain versus the selected fused parent. The change keeps the same input coverage and block-level atomic strategy; measure it against the parent because added live state and guarded loads may offset the benefit.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Replace the single dependent per-thread accumulation chain with four interleaved accumulators, each using its own input sequence separated by the grid stride.",
    "Group four grid-stride positions per loop iteration with an independent bounds check for each load, preserving complete coverage without reading past n.",
    "Retain the fused CUB block reduction, per-block atomic output accumulation, grid sizing, and per-call output reset from the selected T1 parent."
  ]
}
```

## transpose — job 781117

Campagne `transpose`. Pipeline achevé : **False**. Essais : 22. Commit retenu : `63e81efb0ef64c0f37e55a8f1a7b5333da58e83b`. Commit G : `63e81efb0ef64c0f37e55a8f1a7b5333da58e83b`. G confirmé : True.

Objectif naïf de recherche : 0,000016726 s ; retenu : 0,000003291 s ; G : 0,000003291 s.

Erreur de pipeline : ForestError: Submission requires a Makefile and run.sh in the imported repository

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | e7aae98083494a1b | valid | 0,000003221 | d185d8f63ddc4f47c1a453b11b5bfbab123f89fe |
| 2 | T2 | e8a93e7f6ed140ca | valid | 0,000003788 | ed36c2501c926e28f0f78aca074d517d410c00cf |
| 3 | T3 | 22fc3666e09d4964 | valid | 0,000003228 | 573f508c0a9149a1fc90ac8334ff435a651a13c0 |
| 4 | T3 | 410c43d142264f24 | valid | 0,000003271 | 6369a2711d0b6dbbaefbe8e491c68402836011a4 |
| 5 | T1 | 02dc5c5c326d470e | valid | 0,000003385 | 0b6fb62f262d504fb616a0769a5cf799e54b4e73 |
| 6 | T3 | ac430e50aa954744 | valid | 0,000003323 | f909ab8dd40ad95ea5617447b797219f27f56201 |
| 7 | T2 | db17fde880494efb | valid | 0,000003716 | 69f610d9f089cb55212e264dcbf49e15ea17ad02 |
| 8 | T1 | ec69b9eec68b41ad | valid | 0,000003281 | 070e26ce482d23e2bcf85fd1324d3e8d8d6543f5 |
| 9 | T3 | ba49343fcbb34c0c | valid | 0,000004584 | f13b71452d0e8693f674436735cfa8effc802243 |
| 10 | T1 | 20b992b95c314840 | valid | 0,000004356 | 3ce58f611f6331646ac8c746bbbfa356aa2e8a61 |
| 11 | T2 | 3bfa927ccfa942cd | valid | 0,000003656 | 315ae883ecbfa5f8a9c186cc1f19c328fcfe2585 |
| 12 | T3 | 6b1d0f66c6dd42ff | valid | 0,000003177 | 00a7b1a5a33133b6179756ea384015e6343931a6 |
| 13 | T1 | 3b8399b3303842f4 | valid | 0,000003742 | 9ce55dfffb481c2f71ec8472c29978afbb7bb175 |
| 14 | T3 | 6059e5814c18432f | valid | 0,000003190 | e2a7ba9c4daf901591ce8518ce71f9d770a208d1 |
| 15 | T1 | 9aa35d56398e49e7 | valid | 0,000003383 | 6322cd4275810e483f8f1c56b44da4711753a243 |
| 16 | T2 | b42a6fbd66ab4663 | valid | 0,000003888 | 14de8e6dfd5ef8c0c0ef31a940f58b802deda75d |
| 17 | T3 | 423c92789693401a | valid | 0,000004639 | 53117a3f70727d1d460f6645626eb5dd81ebce46 |
| 18 | T1 | eec09365d2824462 | valid | 0,000003928 | 02accad532cb1e1338513f1fbc1727c18500f916 |
| 19 | T2 | 69f6f217fd8b4feb | valid | 0,000003550 | 8399c3600b5c0e5ff5d5bf770590b702a8f4f40d |
| 20 | T3 | 9739a9b338a542d7 | valid | 0,000003255 | 118f3cdf31d1ab860826e5f8a4d18bf25b1cd032 |
| 21 | T1 | 217521c717d746ad | valid | 0,000003725 | 0d63f5ecab10fc23e6449f5aadf110e1a1522ab5 |
| 22 | G | a78d9747308e4ae1 | valid | 0,000003266 | 63e81efb0ef64c0f37e55a8f1a7b5333da58e83b |

### Essai 1 · T1 · e7aae98083494a1b

Parent : `d5ca8c46ce3e071804662035c065c55956797e8e`. Statut mesuré : **valid**.

Hypothèse déclarée : Le baseline lit de façon contiguë mais écrit avec un pas de n entre lanes. Une tuile partagée 32x33 devrait réordonner les données pour rendre les deux passages globaux contigus; les quatre lignes traitées par thread limitent la taille du bloc. La synchronisation et le trafic partagé peuvent toutefois coûter plus que les écritures stridées, donc aucun gain n'est présumé. Le baseline est valide et sa moyenne observée à n=1024 est de 16,712 µs sur trois échantillons.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer l’accès global stridé du transpose naïf par un échange de tuile en mémoire partagée 32x33, avec padding de colonne.",
    "Traiter la tuile avec des blocs 32x8 et des boucles de quatre lignes par thread; permuter les coordonnées de bloc après la synchronisation pour obtenir des accès globaux contigus à l’écriture.",
    "Gérer les bords par prédicats et lancer une grille arrondie au supérieur, sans allocation et en conservant la copie directe des flottants."
  ]
}
```

### Essai 2 · T2 · e8a93e7f6ed140ca

Parent : `d5ca8c46ce3e071804662035c065c55956797e8e`. Statut mesuré : **valid**.

Hypothèse déclarée : Le baseline valide effectue des lectures coalescées mais des écritures à pas n. Un warp peut charger un tile 32x32 par colonnes, échanger les bits lane/registres avec cinq étapes de shuffles XOR, puis écrire par lignes de façon coalescée sans mémoire partagée ni synchronisation CTA. Les 160 shuffles par warp et la pression de registres peuvent toutefois annuler le bénéfice; seule la mesure contrôleur permettra de trancher.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer le transpose naïf par un transpose tuilé 32x32 : chaque warp charge par colonnes, applique en place cinq permutations de bits lane/registres au moyen de shfl.sync.bfly, puis écrit par lignes avec des accès coalescés.",
    "Regrouper quatre warps indépendants par CTA sans communication inter-warp; conserver la participation de toutes les lanes au shuffle et gérer les tuiles partielles par prédication des accès."
  ]
}
```

### Essai 3 · T3 · 22fc3666e09d4964

Parent : `d5ca8c46ce3e071804662035c065c55956797e8e`. Statut mesuré : **valid**.

Hypothèse déclarée : This first candidate establishes the row-major CTA control: a padded shared-memory tile should remove the baseline transpose's strided global stores while preserving coalesced loads and stores. At n=1024 the measured naive baseline averaged 16.712 µs, but this candidate has no measurement yet. A later block-order comparison should hold this kernel, geometry and tile mapping fixed except for a bijective CTA remapping; any locality or partition effect remains a hypothesis to measure.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Replace the naive transpose kernel with a 32x32 shared-memory tile padded to 32x33 and a 32x8 thread block, loading and storing through coalesced tile accesses.",
    "Use direct blockIdx.x/blockIdx.y tile coordinates as the row-major CTA control mapping, with a ceil-divided grid and bounds checks for edge tiles."
  ]
}
```

### Essai 4 · T3 · 410c43d142264f24

Parent : `d5ca8c46ce3e071804662035c065c55956797e8e`. Statut mesuré : **valid**.

Hypothèse déclarée : À géométrie, mapping de données et code intra-CTA constants, la permutation bijective (x,y) → (x+y mod G,x) pourrait modifier la localité ou la pression sur les partitions mémoire. C’est une hypothèse à mesurer : comparer cette variante au contrôle row-major mesuré, surtout avec des mesures répétées de l’exécution complète à n=1024.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer le mapping direct row-major des CTAs par la permutation bijective tile_x=(blockIdx.x+blockIdx.y)%gridDim.x, tile_y=blockIdx.x.",
    "Conserver la tuile partagée 32×33, le bloc 32×8, les accès globaux coalescés, les vérifications de bords et le mapping de données intra-tuile du contrôle row-major."
  ]
}
```

### Essai 5 · T1 · 02dc5c5c326d470e

Parent : `d5ca8c46ce3e071804662035c065c55956797e8e`. Statut mesuré : **valid**.

Hypothèse déclarée : Le candidat précédent, une transposition tuilée 32x33 avec des blocs 32x8, est valide et a mesuré 3,221 µs en moyenne, contre 16,712 µs pour le baseline. Ce candidat conserve le réordonnancement partagé et le padding, mais passe à des blocs 32x4 : chaque thread traite huit lignes au lieu de quatre. Cela teste le compromis entre moins de threads par CTA et davantage de travail séquentiel par thread, sans présumer d'un gain. Les bords sont gérés pour les dimensions positives non multiples de 32.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplace la copie naïve par une transposition via mémoire partagée avec une tuile 32x33, afin de réordonner les accès avant l'écriture.",
    "Passe à des blocs 32x4 : les threads traitent huit lignes par boucle, en conservant des accès globaux contigus et le padding de shared memory.",
    "Utilise une grille arrondie au supérieur et des prédicats aux bords pour prendre en charge les dimensions positives non multiples de 32, sans allocation ni changement d'API ou de flux par défaut."
  ]
}
```

### Essai 6 · T3 · ac430e50aa954744

Parent : `573f508c0a9149a1fc90ac8334ff435a651a13c0`. Statut mesuré : **valid**.

Hypothèse déclarée : Avec le kernel tuilé, sa géométrie et son mapping intra-tuile inchangés, inverser l’ordre des tuiles x sur une ligne de tuiles sur deux est une permutation bijective pour toute grille carrée. Cette variante serpentine pourrait modifier la localité ou le comportement des partitions mémoire, sans que cela soit acquis. Elle contraste avec la permutation diagonale précédente, dont la moyenne mesurée (3,271 µs) était légèrement supérieure au contrôle row-major (3,228 µs).

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer le mapping direct des coordonnées des tuiles par une permutation serpentine : inverser tile_x sur les lignes de tuiles impaires tout en gardant tile_y inchangé.",
    "Conserver le bloc 32×8, la tuile partagée 32×33, le mapping intra-tuile, les accès coalescés et les vérifications de bords."
  ]
}
```

### Essai 7 · T2 · db17fde880494efb

Parent : `ed36c2501c926e28f0f78aca074d517d410c00cf`. Statut mesuré : **valid**.

Hypothèse déclarée : Le parent a déjà une forte amélioration mesurée, mais ses cinq étapes font 160 échanges shuffle par warp et transposent tout le tile en registres. Cette variante conserve les trois échanges des bits faibles puis finalise la permutation par un passage en mémoire partagée paddée. Elle teste si les 64 shuffles évités compensent le transfert partagé et la synchronisation warp; une régression est plausible.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer les cinq étapes de permutation lane/registres par trois étapes de shuffle des bits faibles, puis écrire les 1024 valeurs du tile dans un tampon partagé paddé par warp et relire en ordre de sortie.",
    "Maintenir des tiles warp indépendants, la participation complète au masque de shuffle et à __syncwarp, ainsi que les prédications de bord et des tiles inactifs."
  ]
}
```

### Essai 8 · T1 · ec69b9eec68b41ad

Parent : `d5ca8c46ce3e071804662035c065c55956797e8e`. Statut mesuré : **valid**.

Hypothèse déclarée : Les variantes tuilées antérieures sont valides : la géométrie 32x8 a mesuré 3,221 µs en moyenne, contre 3,385 µs pour 32x4; le baseline a mesuré 16,712 µs. Je conserve la tuile partagée 32x33 et les blocs 32x8, puis remappe bijectivement les lignes de tuiles par `(blockIdx.y + blockIdx.x) % gridDim.y`. Cela teste si l’ordre diagonal des CTAs modifie utilement la répartition des accès mémoire sur GH200, sans changer les accès coalescés par CTA; le coût du modulo ou une dégradation de localité peuvent aussi annuler le bénéfice.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Conserve le réordonnancement des éléments via une mémoire partagée 32x33 avec blocs 32x8.",
    "Applique une permutation diagonale des lignes de tuiles CTA pour tester l’effet de l’ordre de lancement sur la répartition mémoire.",
    "Utilise une grille carrée arrondie et des prédicats aux bords; conserve l’API, le flux par défaut, l’absence d’allocation et la copie directe des flottants."
  ]
}
```

### Essai 9 · T3 · ba49343fcbb34c0c

Parent : `d5ca8c46ce3e071804662035c065c55956797e8e`. Statut mesuré : **valid**.

Hypothèse déclarée : Le remappage Morton est une autre permutation bijective des CTAs, distincte des variantes diagonale et serpentine déjà mesurées. À code intra-CTA, géométrie 32×8, tuile 32×33 et mapping des données constants, il pourrait modifier la localité ou le comportement des partitions mémoire; ce mécanisme reste à mesurer. Les résultats disponibles favorisent légèrement le contrôle row-major (3,228 µs) sur diagonal (3,271 µs) et serpentin (3,323 µs), sans établir de cause. Comparer les mesures répétées de l’exécution complète à n=1024; aucune amélioration n’est présumée.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer la transposition naïve par une transposition tuilée en mémoire partagée 32×33, avec blocs 32×8, transferts globaux coalescés et vérifications des bords.",
    "Remapper les identifiants linéaires row-major des CTAs par décodage Morton lorsque le nombre de tuiles par dimension est une puissance de deux; conserver le mapping row-major sinon."
  ]
}
```

### Essai 10 · T1 · 20b992b95c314840

Parent : `d5ca8c46ce3e071804662035c065c55956797e8e`. Statut mesuré : **valid**.

Hypothèse déclarée : Les variantes observées avec des tuiles 32x33 et des blocs 32x8 sont valides et ont mesuré 3,221 µs, contre 16,712 µs pour le baseline. Cette expérience contraste en utilisant une tuile partagée 64x65 avec des blocs 32x8 : chaque thread traite deux segments de colonnes et huit lignes, ce qui réduit d’un facteur quatre le nombre de CTA à n=1024. La charge par CTA, le travail par thread et l’empreinte partagée augmentent aussi et peuvent annuler tout avantage; aucun gain n’est présumé.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer la copie naïve par une transposition partagée 64x64 à stride 65, avec des CTA de 32x8 threads.",
    "Faire traiter à chaque thread deux segments de 32 colonnes sur huit lignes; conserver les copies directes de float et des accès globaux contigus dans les deux phases.",
    "Arrondir la grille au supérieur, masquer les bords et ne pas lancer de noyau pour n<=0; préserver l’API, le flux par défaut et l’absence d’allocation."
  ]
}
```

### Essai 11 · T2 · 3bfa927ccfa942cd

Parent : `d5ca8c46ce3e071804662035c065c55956797e8e`. Statut mesuré : **valid**.

Hypothèse déclarée : Deux stages de shuffle sur les bits faibles, suivis de la permutation partagée des bits restants, pourraient conserver les accès globaux coalescés tout en réduisant le coût d’échange par rapport au candidat hybride mesuré à trois stages. Les résultats disponibles sont valides : 3,7155 µs pour le hybride à trois stages et 3,7877 µs pour les cinq stages entièrement par shuffle; ils ne suffisent pas à prédire le résultat à deux stages.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer le transpose naïf par un chargement de tuile 32×32 par warp, deux permutations lane/registres via shuffle XOR sur les bits 0 et 1, puis une permutation des coordonnées restantes dans une mémoire partagée paddée.",
    "Conserver quatre warps indépendants par bloc, une région partagée dédiée à chaque warp, la participation complète au masque de shuffle et de __syncwarp, ainsi que le prédicat des accès partiels et des tuiles inactives."
  ]
}
```

### Essai 12 · T3 · 6b1d0f66c6dd42ff

Parent : `d5ca8c46ce3e071804662035c065c55956797e8e`. Statut mesuré : **valid**.

Hypothèse déclarée : Les essais antérieurs ont tous été valides et distincts (source_diversity : 4 programmes), mais le contrôle row-major mesuré à 3,228373 µs reste légèrement devant les mappings diagonal (3,271147 µs), serpentin (3,322560 µs) et Morton (4,583787 µs). Une permutation rotation-réflexion des CTAs, bijective sur la grille carrée, pourrait changer la localité ou le comportement cache/partitions mémoire ; ces effets restent à mesurer. Le code intra-CTA, la géométrie et le mapping des données dans la tuile restent ceux du contrôle row-major. Aucun gain n'est présumé.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Reprendre le kernel tuilé du contrôle row-major : tuile partagée 32×33, blocs 32×8, transferts coalescés, synchronisation et vérifications des bords.",
    "Remapper uniquement les coordonnées de tuiles des CTAs par la bijection tile_x=blockIdx.y, tile_y=gridDim.y-1-blockIdx.x ; garder le mapping intra-tuile et la transposition de sortie inchangés."
  ]
}
```

### Essai 13 · T1 · 3b8399b3303842f4

Parent : `3ce58f611f6331646ac8c746bbbfa356aa2e8a61`. Statut mesuré : **valid**.

Hypothèse déclarée : Les variantes observées avec une tuile 32x33 et des blocs 32x8 mesurent 3,221 µs, tandis que la géométrie 64x65 du parent mesure 4,356 µs; la variante 32x4 mesure 3,385 µs. Cette expérience conserve la tuile 32x33 et passe à des blocs 32x16 : deux fois plus de threads par CTA mais deux fois moins d’itérations par thread que 32x8. Elle teste si ce compromis réduit le coût de boucle ou si la pression accrue en threads/occupation annule l’effet, sans présumer d’un gain.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer la tuile partagée 64x65 du parent par une tuile 32x33 et une grille arrondie correspondante.",
    "Utiliser un bloc 32x16 : chaque thread traite deux lignes, avec des chargements et écritures contigus par warp et une synchronisation entre les deux phases.",
    "Masquer les lignes et colonnes hors limites; conserver l’API, la copie directe des valeurs, le flux par défaut et l’absence d’allocation."
  ]
}
```

### Essai 14 · T3 · 6059e5814c18432f

Parent : `d5ca8c46ce3e071804662035c065c55956797e8e`. Statut mesuré : **valid**.

Hypothèse déclarée : Le contrôle row-major mesuré à 3,228373 µs a été légèrement plus rapide que les mappings diagonal (3,271147 µs), serpentin (3,322560 µs) et Morton (4,583787 µs), tandis qu'une rotation-réflexion a mesuré 3,177493 µs. Ces résultats ne démontrent pas de cause. Cette expérience teste un échange simple des coordonnées CTA (tileX=blockIdx.y, tileY=blockIdx.x), susceptible de modifier l'ordre des tuiles exécutées. Le code intra-CTA, la géométrie 32×8 et le mapping des éléments dans la tuile 32×33 restent fixes; un effet sur localité, cache ou partitions mémoire reste à mesurer.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer la transposition naïve par une transposition en tuile partagée 32×33, avec blocs 32×8 et lectures/écritures globales coalescées.",
    "Remapper uniquement les coordonnées des tuiles des CTA en échangeant blockIdx.x et blockIdx.y; conserver le mapping de données et le calcul intra-tuile de la transposition standard."
  ]
}
```

### Essai 15 · T1 · 9aa35d56398e49e7

Parent : `0b6fb62f262d504fb616a0769a5cf799e54b4e73`. Statut mesuré : **valid**.

Hypothèse déclarée : Les cinq programmes distincts observés sont valides. La tuile 32x33 avec blocs 32x8 a mesuré 3,221 µs, contre 3,385 µs pour le parent 32x4; la variante 32x16 a mesuré 3,742 µs. Cette expérience teste 32x2 (64 threads par CTA, 16 itérations de lignes par thread) : moins de threads par CTA pourrait réduire les ressources consommées, mais davantage de travail séquentiel ou moins de parallélisme pourrait dégrader le temps. Aucun gain n’est présumé; les temps répétés de l’exécution complète à n=1024 restent à mesurer.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Conserver la transposition partagée 32x33 et changer BLOCK_ROWS de 4 à 2, soit un CTA de 32x2 threads et 16 itérations par thread.",
    "Conserver les accès globaux coalescés, le masquage des bords, la copie directe des flottants, l’API existante, le flux par défaut et l’absence d’allocation."
  ]
}
```

### Essai 16 · T2 · b42a6fbd66ab4663

Parent : `69f610d9f089cb55212e264dcbf49e15ea17ad02`. Statut mesuré : **valid**.

Hypothèse déclarée : Un quatrième échange shuffle des bits lane/registres pourrait réduire la permutation résiduelle à effectuer par mémoire partagée, mais ajoute des instructions shuffle. Cette variante teste ce compromis par rapport aux hybrides mesurés à deux et trois étapes; le résultat peut être négatif si le shuffle supplémentaire coûte davantage que le changement de permutation partagée.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Effectuer quatre étapes de permutation lane/registres par shuffle XOR, sur les bits 0 à 3, avec participation complète de toutes les lanes du warp.",
    "Terminer la permutation du bit restant avec un tampon partagé paddé par warp, une synchronisation warp et des accès de sortie coalescés; conserver les prédicats des tuiles partielles et inactives."
  ]
}
```

### Essai 17 · T3 · 423c92789693401a

Parent : `d5ca8c46ce3e071804662035c065c55956797e8e`. Statut mesuré : **valid**.

Hypothèse déclarée : Les six programmes T3 mesurés sont distincts et valides, mais leurs temps à n=1024 varient : le contrôle row-major est à 3,228 µs, plusieurs permutations sont proches (3,177–3,323 µs) et Morton est à 4,584 µs. Ce nouvel essai applique Gray(q)=q^(q>>1) à l’identifiant linéaire des CTAs sur les grilles carrées de taille puissance de deux. Il teste un ordre différent en gardant fixes la tuile 32×33, le bloc 32×8 et le mapping des éléments intra-tuile. Un effet sur la localité ou le cache reste une hypothèse à mesurer.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer le lancement naïf par une transposition partagée 32×33, blocs 32×8, lectures et écritures coalescées, avec masquage des bords.",
    "Pour les grilles carrées dont le côté est une puissance de deux, permuter les CTA par Gray-codage de leur identifiant linéaire; utiliser row-major pour les autres grilles sans modifier le mapping intra-tuile."
  ]
}
```

### Essai 18 · T1 · eec09365d2824462

Parent : `3ce58f611f6331646ac8c746bbbfa356aa2e8a61`. Statut mesuré : **valid**.

Hypothèse déclarée : Le parent sélectionné (tuile 64x65, CTA 32x8) est valide mais a mesuré 4,356 µs, contre 3,221 µs pour la meilleure variante observée en 32x33 et 32x8. Cette expérience conserve la transposition partagée, mais teste une tuile 32x33 avec des transferts globaux uint4 par thread et un CTA 8x32 : moins d’instructions globales pourrait aider, tandis que les transferts de partage scalaires et le regroupement de plusieurs lignes par warp pourraient annuler le gain. Les temps répétés de l’exécution complète et la correction à n=32,64,256,1024 restent à mesurer par le contrôleur.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer le chemin principal 64x65 par une transposition partagée 32x33 avec CTA 8x32, chacun effectuant un chargement et un stockage global uint4 sous forme de bits non interprétés.",
    "Conserver un chemin scalaire tuilé 32x33 pour les dimensions non multiples de quatre ou les pointeurs non alignés; masquer les bords dans les deux noyaux.",
    "Préserver l’API, le flux par défaut, l’absence d’allocation, le retour pour n<=0 et la copie bit-exacte."
  ]
}
```

### Essai 19 · T2 · 69f6f217fd8b4feb

Parent : `ed36c2501c926e28f0f78aca074d517d410c00cf`. Statut mesuré : **valid**.

Hypothèse déclarée : Une seule étape de shuffle sur un bit de coordonnée, suivie d’une permutation explicite en mémoire partagée paddée par warp, pourrait être plus rapide que les variantes hybrides à deux ou trois étapes si le shuffle évité compense le transfert partagé restant. Le meilleur hybride mesuré à deux étapes vaut 3,6557 µs à n=1024 contre 3,7877 µs pour les cinq étapes entièrement par shuffle; cette variante à une étape teste un compromis distinct et peut aussi régresser si le transfert partagé domine.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer le transpose entièrement par shuffles par un hybride : charger la tuile 32×32, échanger un bit lane/registres avec __shfl_xor_sync, puis calculer les coordonnées finales et permuter par warp via une mémoire partagée paddée.",
    "Garder quatre warps indépendants par bloc avec des zones partagées séparées; faire participer toutes les lanes au shuffle et à __syncwarp, y compris pour les tuiles partielles et inactives, et prédicater les accès globaux aux bords."
  ]
}
```

### Essai 20 · T3 · 9739a9b338a542d7

Parent : `d5ca8c46ce3e071804662035c065c55956797e8e`. Statut mesuré : **valid**.

Hypothèse déclarée : Les mappings CTA testés précédemment ont donné des résultats valides mais variés : le contrôle row-major a mesuré 3,228 µs à n=1024, le mapping diagonal 3,271 µs et une rotation-réflexion 3,177 µs. Je teste une autre permutation affine du carré de tuiles, (tile_x,tile_y)=(bx+2by,bx+by) modulo G. Elle est bijective pour tout G positif et ne change ni la géométrie 32×8, ni le code intra-CTA, ni le mapping des éléments dans la tuile. Un effet de l’ordre sur la localité ou les caches reste à mesurer; aucun gain n’est présumé.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer la transposition naïve par une transposition partagée tuilée 32×33 avec blocs 32×8, accès globaux coalescés et vérifications de bords.",
    "Remapper uniquement les coordonnées CTA avec (tile_x,tile_y)=(bx+2by,bx+by) modulo G; utiliser une réduction par soustraction conditionnelle et conserver le code intra-CTA et les coordonnées de données transposées."
  ]
}
```

### Essai 21 · T1 · 217521c717d746ad

Parent : `d5ca8c46ce3e071804662035c065c55956797e8e`. Statut mesuré : **valid**.

Hypothèse déclarée : Les mesures fournies placent la transposition 32x33 avec CTA 32x8 à 3,221 µs, meilleure que le baseline à 16,712 µs et que les géométries 32x2, 32x16 et 64x65 déjà mesurées. Le catalogue compte sept programmes distincts et valides, sans répétition. Je conserve le schéma tuilé 32x33/32x8 et teste une permutation diagonale bijective des CTA : pour les grandes grilles à strides puissance de deux, une distribution différente des tuiles peut réduire les conflits de partitions mémoire, mais le calcul modulo peut aussi annuler tout bénéfice. Aucun gain n’est présumé.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Remplacer la copie naïve par une transposition partagée 32x33 avec CTA 32x8 et accès globaux contigus dans les deux phases.",
    "Réordonner bijectivement les coordonnées des CTA par une permutation diagonale de la grille carrée, en conservant le traitement complet de chaque tuile.",
    "Masquer les bords pour les tailles positives non multiples de 32, garder le flux par défaut et ne pas allouer de mémoire."
  ]
}
```

### Essai 22 · G · a78d9747308e4ae1

Parent : `00a7b1a5a33133b6179756ea384015e6343931a6`. Statut mesuré : **valid**.

Hypothèse déclarée : La transposition tuilée en mémoire partagée préserve des lectures et écritures globales coalescées ; le remappage bijectif des CTAs est le candidat de recherche le plus rapide actuellement. La confirmation indépendante de cette intégration reste à obtenir.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cu"
  ],
  "retained": [
    "Conserver le kernel de transposition avec une tuile partagée paddée de 32x33 et un CTA de 32x8, assurant des accès globaux coalescés.",
    "Réordonner les coordonnées des tuiles CTA par tile_x=blockIdx.y et tile_y=gridDim.y-1-blockIdx.x, une bijection sur la grille carrée.",
    "Préserver le point d’entrée, le flux CUDA par défaut, l’absence d’allocation et la copie bit-exacte de A vers C transposée."
  ]
}
```

## utf8 — job 781175

Campagne `utf8`. Pipeline achevé : **True**. Essais : 7. Commit retenu : `ad28ccd027ca3adf78cf7293b0aa7ff37e72a855`. Commit G : `ad28ccd027ca3adf78cf7293b0aa7ff37e72a855`. G confirmé : True.

Objectif naïf de recherche : 0,000050787 s ; retenu : 0,000021038 s ; G : 0,000021038 s.

Début UTC : 2026-10-23T17:15:09.797801+00:00 ; durée murale : 1768,9 s ; dépassement cible déclaré : 0,0 s.

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | 5bc7ec895d84471a | valid | 0,000031886 | d714008fb7e84467df7f384a50bbcdce9d9a3af9 |
| 2 | T2 | 39f91920ea4d45f6 | valid | 0,000059595 | 8750e733a1380a96df073edb4d844e6ba62dced3 |
| 3 | T3 | fe9422da2eba4910 | valid | 0,000086838 | 750b3f8127dde1f1551c177a4a5e9e759266564d |
| 4 | T2 | 047f64c45a214d0f | valid | 0,000061453 | c2110b258cdc9f72edade185d13105159ffbf004 |
| 5 | T1 | e88ccb3a728642dc | valid | 0,000022198 | fe3cb254b06a994088d58afad2f1cd4439c53198 |
| 6 | T2 | 8813b0c4e6de4154 | valid | 0,000054515 | 194a720e7e720e268041cac714db6e496e974b19 |
| 7 | G | 53bcdc7656ac4008 | valid | 0,000021088 | ad28ccd027ca3adf78cf7293b0aa7ff37e72a855 |

### Essai 1 · T1 · 5bc7ec895d84471a

Parent : `d3db76a81d4d8c1c124b8d98156600dfb9c0000d`. Statut mesuré : **valid**.

Hypothèse déclarée : A 16-byte SSE2 scan can classify ASCII, continuation, and valid leading-byte classes in parallel, then compare masks for the exact continuation structure and second-byte restrictions. Carrying the remaining continuation count and any restricted second-byte rule across block boundaries should avoid scalar per-byte validation for large inputs; a bounds-checked scalar tail preserves correctness for all lengths. The baseline has only one measured outcome, so this is a candidate hypothesis, not a claimed speedup.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Use 16-byte SSE2 unaligned loads and movemasks to classify byte categories and valid lead-byte classes.",
    "Check exact continuation masks and overlong, surrogate, and Unicode upper-bound second-byte restrictions using shifted bit masks.",
    "Carry incomplete continuation counts and any special second-byte restriction between blocks; use a bounds-checked scalar validator for the tail."
  ]
}
```

### Essai 2 · T2 · 39f91920ea4d45f6

Parent : `d3db76a81d4d8c1c124b8d98156600dfb9c0000d`. Statut mesuré : **valid**.

Hypothèse déclarée : On long ASCII spans, checking eight bytes at once with a scalar high-bit mask should reduce per-byte loop overhead compared with the baseline. Mixed-width words fall back to the exact scalar UTF-8 parser; whether the added word loads help this workload remains to be measured.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Check complete eight-byte input chunks using memcpy and a scalar high-bit mask; skip only chunks whose bytes are all ASCII.",
    "Use the existing exact scalar UTF-8 validation rules when a word contains a non-ASCII byte, with remaining-length checks before multibyte reads.",
    "Write the complete uint32_t result using memcpy, preserving the run ABI."
  ]
}
```

### Essai 3 · T3 · fe9422da2eba4910

Parent : `d3db76a81d4d8c1c124b8d98156600dfb9c0000d`. Statut mesuré : **valid**.

Hypothèse déclarée : Skipping complete all-ASCII 64-bit words at DFA accept boundaries may reduce per-byte branch overhead on long ASCII runs while leaving validation of non-ASCII and mixed input to the existing byte-class/state tables. The memcpy and remaining-length guard avoid alignment assumptions and tail overreads. Frequent non-ASCII bytes may make the extra word probe neutral or slower; controller measurements should determine the effect.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "At DFA accept boundaries, skip complete 64-bit words only when their high-bit mask is clear; use memcpy for unaligned-safe loads and a remaining-length check to protect tails, then retain the scalar ASCII and table-driven DFA paths."
  ]
}
```

### Essai 4 · T2 · 047f64c45a214d0f

Parent : `8750e733a1380a96df073edb4d844e6ba62dced3`. Statut mesuré : **valid**.

Hypothèse déclarée : The selected parent’s correct 8-byte scan averaged 59.59 µs versus the baseline’s 49.64 µs. A contrasting 32-byte ASCII probe using four safe word loads and an OR-reduced high-bit test may reduce loop overhead on long ASCII spans. Blocks containing non-ASCII bytes incur extra probes before the same exact scalar parser runs, so the mixed-width workload may instead regress; no speedup is assumed.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Probe complete 32-byte input blocks using four memcpy-based uint64_t loads; advance only when the OR-reduced high-bit mask is clear.",
    "Retain guarded 8-byte ASCII skips for remaining complete words; process possible non-ASCII bytes and short tails with the exact scalar UTF-8 checks.",
    "Preserve the run ABI, full uint32_t output write, and serial execution."
  ]
}
```

### Essai 5 · T1 · e88ccb3a728642dc

Parent : `d3db76a81d4d8c1c124b8d98156600dfb9c0000d`. Statut mesuré : **valid**.

Hypothèse déclarée : Replacing the SIMD prefix-sum state calculation with an integer mask of expected continuation positions may reduce per-block work while retaining SIMD byte classification. The mask explicitly carries up to three required bytes across blocks; a bounds-checked scalar tail handles all remaining lengths. An ASCII-block fast path tests whether common blocks can bypass classification. This contrasts with the previously measured direct SIMD candidate; performance remains unverified for this variant.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Replace the vector prefix-sum continuation-debt calculation with a scalar bit mask derived from SIMD lead-byte masks, checking exact continuation positions and carrying overflow bits to the next block.",
    "Retain SIMD classification and restricted-second-byte checks for complete 16-byte blocks, including the preceding-block boundary byte.",
    "Use a bounds-checked scalar validator for the final 0–15 bytes and carry pending sequence state into and through the tail.",
    "Add a fast path for complete all-ASCII blocks when no continuation debt is pending."
  ]
}
```

### Essai 6 · T2 · 8813b0c4e6de4154

Parent : `d3db76a81d4d8c1c124b8d98156600dfb9c0000d`. Statut mesuré : **valid**.

Hypothèse déclarée : The correct 8-byte scan (59.59 µs) and 32-byte probe (61.45 µs) both measured slower than the 49.64 µs baseline on this workload. A 16-byte probe using two safe scalar word reads may balance fewer probes against larger-block overhead; the results do not establish why earlier variants regressed, and no speedup is assumed.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Probe complete 16-byte spans using two memcpy-based uint64_t loads and skip only when both words contain ASCII bytes.",
    "Fall back to the exact scalar UTF-8 checks for non-ASCII bytes, with remaining-length checks before multibyte reads.",
    "Preserve the run ABI, serial execution, and full uint32_t output overwrite using memcpy."
  ]
}
```

### Essai 7 · G · 53bcdc7656ac4008

Parent : `fe3cb254b06a994088d58afad2f1cd4439c53198`. Statut mesuré : **valid**.

Hypothèse déclarée : Keep the fastest correct measured SIMD validator and test whether branching around restricted second-byte range checks helps: for blocks with no E0, ED, F0, or F4 immediately before a lane, skip the additional range-mask operations. This is an unmeasured hypothesis about the workload, not a claimed speedup.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Retain e88's 16-byte SSE2 byte classification, continuation-position mask and cross-block carry.",
    "After structural validation, return early from restricted-byte checks when no E0, ED, F0, or F4 precedes a lane; otherwise perform the original exact range checks.",
    "Keep the bounds-checked scalar tail and the original ABI and full uint32 output overwrite."
  ]
}
```

## volume — job 781192

Campagne `volume`. Pipeline achevé : **True**. Essais : 4. Commit retenu : `9fbb1576cf62e5f738c85df1d8067012723ffc29`. Commit G : `9fbb1576cf62e5f738c85df1d8067012723ffc29`. G confirmé : True.

Objectif naïf de recherche : 5,267984178 s ; retenu : 1,018930485 s ; G : 1,018930485 s.

Début UTC : 2026-10-23T18:02:46.863069+00:00 ; durée murale : 2453,6 s ; dépassement cible déclaré : 653,6 s.

| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |
|---:|---|---|---|---:|---|
| 1 | T1 | ccda6fb421d24fbb | valid | 1,126709885 | 6877fec993c5630399be208a3e0fb1cacaaf307a |
| 2 | T2 | c0c1409f7a654dc0 | valid | 5,129965758 | 3186680600414587bf294c71200305ffe0473f6e |
| 3 | T3 | a40da77848074776 | valid | 5,046921197 | 51d560f42bd0d000bd0ce8289d29a788188e4648 |
| 4 | G | 8027a48afd1342cf | valid | 1,018177683 | 9fbb1576cf62e5f738c85df1d8067012723ffc29 |

### Essai 1 · T1 · ccda6fb421d24fbb

Parent : `c56c3c0c97e5d86266a00a9e02bf95b512579c98`. Statut mesuré : **valid**.

Hypothèse déclarée : Chaque pixel écrit un emplacement distinct et les données de volume/caméra ne sont lues que par rayon. Un parcours OpenMP statique des pixels devrait exploiter jusqu’au budget demandé via num_threads(threads), tandis que le cas threads <= 1 conserve une exécution sérielle. Les calculs par rayon restent inchangés.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Ajout d’un parcours OpenMP statique sur les pixels avec collapse(2) et num_threads(threads) pour plafonner l’équipe au budget reçu.",
    "Conservation d’un chemin sériel explicite quand threads <= 1 et d’un wrapper conservant l’ancienne signature de volume_serial.",
    "Calcul de l’index image par pixel avec std::size_t; aucune modification du calcul de rayon, de l’interpolation ou des pas d’échantillonnage."
  ]
}
```

### Essai 2 · T2 · c0c1409f7a654dc0

Parent : `c56c3c0c97e5d86266a00a9e02bf95b512579c98`. Statut mesuré : **valid**.

Hypothèse déclarée : Dans chaque interpolation, les huit D précédents recalculaient chacun trois clamps et une adresse tridimensionnelle aplatie. Pré-calculer les six indices voisins clampés, les deux offsets de tranche, les deux offsets de ligne et réutiliser quatre pointeurs de ligne devrait réduire ces calculs sans toucher au test de volume, aux coordonnées, à leur conversion, ni à l’ordre des Lerp. Le baseline correct rapporte une moyenne de 5,2729 s; aucun gain du candidat n'est encore établi.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Déplacer les six clamps de coordonnées voisines dans Density afin de les exécuter une seule fois par interpolation.",
    "Calculer et réutiliser les offsets des deux tranches et des deux lignes; réduire D à un accès à une ligne et conserver l'ordre des Lerp."
  ]
}
```

### Essai 3 · T3 · a40da77848074776

Parent : `c56c3c0c97e5d86266a00a9e02bf95b512579c98`. Statut mesuré : **valid**.

Hypothèse déclarée : Les rayons d’ombre partent généralement d’un échantillon strictement intérieur au volume. Dans ce cas, après le clamp du paramètre d’entrée à zéro, seul le paramètre de sortie est nécessaire : choisir directement la face de sortie sur chaque axe évite les calculs des trois paramètres d’entrée et les permutations. Les directions nulles, non comparables, et les origines sur ou hors du volume conservent l’intersection générale. Le pas, les positions échantillonnées et l’accumulation de tau ne changent pas; le contrôleur devra valider les six cas et mesurer séparément la performance.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Ajout d’IntersectShadowP : pour une origine strictement dans le volume et des composantes de direction non nulles et ordonnées, calcule directement la paramétrisation de sortie sur chaque axe et conserve le clamp d’entrée à zéro; tous les autres cas utilisent IntersectP inchangé. L’appelle uniquement depuis transmittance."
  ]
}
```

### Essai 4 · G · 8027a48afd1342cf

Parent : `6877fec993c5630399be208a3e0fb1cacaaf307a`. Statut mesuré : **valid**.

Hypothèse déclarée : Combiner OpenMP du candidat le plus rapide avec les réductions indépendantes des calculs d’interpolation et d’intersection des rayons d’ombre devrait préserver le résultat tout en réduisant le travail par pixel. Le bénéfice de cette combinaison n’a pas été mesuré.

Transformations déclarées :

```json
{
  "files": [
    "src/candidate.cpp"
  ],
  "retained": [
    "Conserver le parcours parallèle OpenMP statique des pixels et le chemin sériel pour threads <= 1 de T1.",
    "Remplacer les appels répétés de clamps et d’adressage de Density par six indices clampés et des pointeurs de lignes réutilisés; préserver l’ordre des Lerp de T2.",
    "Ajouter un chemin d’intersection spécialisé pour les origines strictement intérieures des rayons d’ombre; utiliser IntersectP pour les cas limites ou directions dégénérées, selon T3."
  ]
}
```

## Limites de ce journal

Les résultats indépendants du tableau principal priment sur le classement de recherche. Un essai invalide n’est pas un gain de performance. Une erreur d’infrastructure n’est pas traitée comme un algorithme incorrect. Les références optimisées n’ont pas été transmises au modèle. Les compteurs cumulés de tokens ne sont pas additionnés ici.
