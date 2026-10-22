# Dataset acquisition and preparation

## Data sources

The preferred academic source is [CICIDS2017 from the Canadian Institute for Cybersecurity](https://www.unb.ca/cic/datasets/ids-2017.html), listed on the [official CIC dataset index](https://www.unb.ca/cic/datasets/index.html). The official page describes PCAPs and labeled flow CSVs produced with CICFlowMeter and reports 7.8–13 GB for each weekday capture. Check the current page, download form, disk space, and any license/citation requirements before obtaining data. This project does not download the dataset automatically.

The official CSV feature set contains 80+ CICFlowMeter measurements. It is not the same as this project's versioned 32-feature schema. Do not pass the original CSV directly into model training or assume its rows map one-to-one to flows generated here. The official site also states that it does not provide file-level PCAP-to-CSV correspondence. A valid training table must be produced from the same flow/feature code used by inference, with verified ground-truth labels.

Dataset paper cited by the official page:

> Iman Sharafaldin, Arash Habibi Lashkari, and Ali A. Ghorbani, “Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization,” 4th International Conference on Information Systems Security and Privacy (ICISSP), 2018.

## Build a labeled feature table

1. Place an authorized PCAP outside Git (the `ml/data/raw/` and `ml/data/derived/` directories are ignored).
2. Generate stable flow IDs and a blank label template:

   ```powershell
   python -m ml.data.export_features `
     --pcap .\ml\data\raw\capture-a.pcap `
     --capture-group capture-a `
     --write-label-template .\ml\data\derived\capture-a-labels.csv
   ```

3. Fill the `label` column only from verified ground truth. Never infer a label from the model's own prediction. Leave no row unlabeled.
4. Replay the same capture and export the schema-compatible features:

   ```powershell
   python -m ml.data.export_features `
     --pcap .\ml\data\raw\capture-a.pcap `
     --capture-group capture-a `
     --labels .\ml\data\derived\capture-a-labels.csv `
     --output .\ml\data\derived\capture-a-features.csv
   ```

5. Repeat for independent capture groups and combine the per-capture files:

   ```powershell
   python -m ml.data.combine_features `
     --input .\ml\data\derived\capture-a-features.csv `
     --input .\ml\data\derived\capture-b-features.csv `
     --output .\ml\data\derived\labeled-flows.csv
   ```

6. Create a manifest that records the prepared table checksum and source provenance:

   ```powershell
   python -m ml.data.manifest `
     --csv .\ml\data\derived\labeled-flows.csv `
     --dataset-name "CICIDS2017 project-schema export" `
     --source-url "https://www.unb.ca/cic/datasets/ids-2017.html" `
     --citation "Sharafaldin, Lashkari, and Ghorbani, ICISSP 2018" `
     --output .\ml\data\derived\dataset-manifest.json
   ```

   Add `--upstream-checksum NAME=SHA256` for each original file checksum that the source publishes or that you compute locally.

7. Train and create a model plus metadata and held-out evaluation report:

   ```powershell
   python -m ml.training.train `
     --csv .\ml\data\derived\labeled-flows.csv `
     --manifest .\ml\data\derived\dataset-manifest.json `
     --output .\ml\models\nids-model.joblib
   ```

The split requires at least five independent capture groups and every class in train, validation, and test. If the data cannot satisfy that group-aware split, the pipeline stops with a specific error rather than falling back to a row split. Dataset and label quality remain the operator's responsibility and must be described in the report.
