## HUPA-UCM Diabetes Dataset (T1DM) — README

### Overview
The **HUPA-UCM Diabetes dataset** is a real-world, multimodal dataset from **25 people with Type 1 Diabetes Mellitus (T1DM)**. It is intended for research on **glucose prediction**, **hypoglycemia/hyperglycemia detection**, and analysis of **lifestyle and physiological factors** affecting glycemic control. Data were collected in **free-living conditions** for **at least 14 days per participant**.

- **Site:** Hospital Universitario Príncipe de Asturias (Alcalá de Henares, Spain)  
- **Ethics approval:** Dec 12, 2018 (Protocol **EC/11/2018**)  
- **Public release:** April 2024 (Mendeley Data)

**Dataset link:** https://data.mendeley.com/datasets/3hbcscwz44/1

---

### Cohort Characteristics
| Attribute | Value |
|---|---|
| Participants | 25 (T1DM) |
| Sex | 52% female |
| Age (years) | 39.23 ± 11.84 |
| HbA1c (%) | 7.37 ± 0.82 |
| Diabetes duration (years) | 17.8 ± 10.5 |
| Monitoring duration | ≥ 14 days/person |

---

### Data Modalities
| Modality | Examples / Notes |
|---|---|
| CGM glucose | Interstitial glucose (mg/dL) |
| Insulin | Basal + bolus doses |
| Meals (carbs) | Recorded as carbohydrate intake (participant-estimated) |
| Activity | Steps, calories burned |
| Physiology | Heart rate |
| Sleep | Sleep quality/quantity assessed in study context |

**Known limitation:** carbohydrate intake for meals is **estimated by participants**, which may introduce labeling error.

---

### Devices & Data Sources
#### CGM
| Component | Detail |
|---|---|
| CGM device | Abbott **FreeStyle Libre 2** |
| Native sampling | Every **15 minutes** |
| Notes | Single CGM model across all participants (no multi-device glucose normalization required) |

#### Insulin delivery
| Therapy type | Participants | Devices / Recording method |
|---|---:|---|
| CSII (pump) | 56% (14/25) | Medtronic or Roche pumps; insulin & carbs extracted from pump data |
| MDI (injections) | 44% (11/25) | Basal/bolus & carbs recorded via a mobile app |

---

### Preprocessing & Normalization
Preprocessing was performed with **glUCModel** (ABSys research group, Universidad Complutense de Madrid) to harmonize data streams.

#### Common time base
All channels were standardized to a **5-minute sampling grid**.

#### Variable-specific normalization (high level)
| Signal | Original sampling / format | 5-minute normalization approach |
|---|---|---|
| Glucose (CGM) | 15-min samples | Rounded to nearest 5 min, resampled; gaps filled via **linear interpolation** |
| Bolus insulin | Event-based doses | Resampled by **summing doses** within each 5-min window |
| Basal insulin (CSII) | Typically rate-based (e.g., U/hour) | Converted to 5-min amounts (e.g., divide appropriately); overlapping intervals summed; missing set to **0** |
| Carbs | Event-based grams | Summed within 5-min windows; converted to **servings** (1 serving = **10 g** carbs); missing set to **0** |
| Heart rate | Device stream | Rounded/resampled to 5 min; missing filled by **linear interpolation** |
| Steps | 1-min counts | Summed into 5-min bins; missing set to **0** |
| Calories | 1-min values | Summed into 5-min bins; missing set to **0** |

#### Handling CSII vs MDI (unification strategy)
The dataset unifies insulin delivery methods by:
- **Temporal standardization:** all insulin information placed on the same **5-min grid**
- **Rate-to-dose conversion:** CSII basal rates converted to fixed-interval doses
- **Aggregation:** overlapping/within-window values summed
- **Gap filling:** absent intervals set to **0**

---

### File Organization & Format
- **One CSV file per participant**
- **Semicolon-separated** fields
- Timestamp format: `yyyy-MM-dd'T'HH:mm:ss`

#### Core columns (per file)
| Column | Units / Type |
|---|---|
| `time` | timestamp |
| `glucose` | mg/dL |
| `calories` | summed per 5 min |
| `heart_rate` | bpm |
| `steps` | summed per 5 min |
| `basal_rate` | standardized to 5-min representation |
| `bolus_volume_delivered` | insulin units delivered in window |
| `carb_input` | **servings** (1 serving = 10 g carbs) |

#### Data quality filtering
To improve consistency, the creators selected **continuous ranges** where both **glucose and heart rate** were present, removing leading/trailing periods lacking valid values for these key signals.

---

### Intended Use Cases
| Task | Examples |
|---|---|
| Glucose forecasting | short-horizon prediction, multi-step prediction |
| Event detection | hypoglycemia / hyperglycemia detection and prediction |
| Lifestyle/physiology analysis | impact of meals, insulin, activity, sleep, heart rate on glycemic control |
| ML benchmarking | multimodal time-series modeling with unified 5-min sampling |

---

### References (primary)
- Dataset: https://data.mendeley.com/datasets/3hbcscwz44/1  
- Companion article (PMC): https://pmc.ncbi.nlm.nih.gov/articles/PMC11214197/  
- PubMed record: https://pubmed.ncbi.nlm.nih.gov/38948410/