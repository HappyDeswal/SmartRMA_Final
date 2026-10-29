# SmartRMA hardware recognition training

This trains **MobileNetV3 Small**, initialized with ImageNet weights, to recognize
`graphics_card`, `motherboard`, `ram`, and `ssd`. It is an auxiliary model in
Node 3. The existing local Ollama vision/text models and the return rules remain.
It does **not** fine-tune Qwen3-VL, learn damage labels, establish electrical
function, authenticate a product, or authorize a return.

## Dataset and attribution

The prepared dataset contains 971 original photographs after auditing: 152 GPUs,
376 motherboards, 312 RAM modules, 131 SSDs. These are source category labels;
they have not all been manually verified. Product boxes, mixed scenes and small
subjects can be present. Sample contact sheets were reviewed; full relabeling
and an independent customer-photo evaluation are still needed.

- Asaniczka (2024), [PC Parts Images Dataset, version 1](https://www.kaggle.com/datasets/asaniczka/pc-parts-images-dataset-classification),
  DOI 10.34740/KAGGLE/DSV/7565076. Kaggle lists ODC-By for the database. The
  photographs were gathered from web sources; underlying image copyrights remain
  with their owners. Do not assume unrestricted redistribution or commercial rights.
- Hasan, Rupin, Fahim, Chowdhury, Rashid, Ali and Niloy (2024),
  [Laptop Components, version 4](https://data.mendeley.com/datasets/pwctygncrj/4),
  DOI 10.17632/pwctygncrj.4, CC BY 4.0. Only the 140 original files in each of
  Raw Data / Motherboard, RAM and SSD are fetched. Pre-augmented images are excluded.

Each retained photograph has its original source filename, source, license,
SHA-256, decoded-pixel hash, pHash and assigned split in `manifest.json`.
Conflicting labels and exact duplicates are excluded. pHash distance <= 6 forms
connected groups before splitting. Training-only augmentations do not count
toward the image total. Split: 679 train, 147 validation, 145 test; all four
classes occur in each split. At least 501 original training photographs are
required by both preparation and training scripts.

**Limits:** no physical-unit IDs are available, so different views of the same
unit may still occur across splits. In particular, SSD photography comes from a
small academic collection. These are exploratory held-out recognition results,
not a unit-disjoint industrial benchmark or evidence of better RMA decisions.
There are no damaged/undamaged labels; none are invented from filenames or LLM
guesses. No product-only photograph is labeled as clean by this pipeline.

## Reproduce on Google Colab

The user's notebook is [SMART_RMA](https://colab.research.google.com/drive/1OQ95qBQjOHOU2JSHR37g50_sAJ7_2gv3).
Select a free T4 GPU runtime. There are no API keys or paid inference services.
Dataset and initial ImageNet weights require internet downloads during training.
The final application runs inference locally.

Use the companion `SmartRMA_Hardware_Training.ipynb`, or upload the prepared
`smartrma_training_input.zip` into Colab session storage and run the supplied
setup, training and export cells. The input bundle includes scripts, the manifest,
audit report and retained images; no customer case data is included.

To build from public sources instead, upload the two Python scripts, then:

```python
%pip install -r requirements-colab.txt
!python prepare_dataset.py --output data/hardware
!python train_hardware.py --data data/hardware --output runs/hardware --epochs 12
```

The pretrained frozen-backbone nearest-centroid classifier is the baseline.
Fine-tuning uses class-weighted loss and training-only augmentation. The best
epoch is chosen on validation macro F1. A scalar temperature is fitted on
validation negative log likelihood. Test examples never select an epoch,
temperature or hyperparameters. Metrics include per-class precision/recall/F1,
accuracy, macro F1, confusion matrix and per-example predictions.

Only one configuration is evaluated here; repeated test-guided tuning would
require a new independent final test set. The baseline comparison is against
frozen ImageNet features, **not** against the existing Qwen3-VL model.

## Install the export locally

From the project root, after downloading the ZIP produced by Colab:

```bash
python -m pip install -r requirements-hardware.txt
python training/install_model.py /path/to/smartrma_hardware_bundle.zip
python run.py
```

Node 3 automatically loads `var/models/hardware` if installed. To use a different
directory, set `HAPPY_HARDWARE_MODEL_DIR=/path/to/export`; set that variable to an
empty string to disable the classifier. Restart the application after installation.
Startup checks the ONNX and metrics checksums, preprocessing, class order and
tensor interface. Missing dependencies, corrupt files or prediction errors
disable/omit the advisory result and preserve the existing condition workflow.
Model health appears in `/api/system` under the vision model inventory.

The recognition score is attached to an observation's `hardware_hint`, persisted
in signed history and shown in case details. It never substitutes for condition
confidence, changes product intake, adds risk, or bypasses T4 human approval.
Images outside the four classes can still receive high scores; this classifier
has no validated out-of-distribution detector. Do not use its score as proof
that an image contains valid hardware.

The ONNX export is numerically compared with PyTorch. `hardware.pt` is retained
for research continuation; serving loads only ONNX and never unpickles `.pt`.
All generated data and weights are ignored by Git; retain the export ZIP and
training inputs outside the disposable Colab runtime.

## Measured run: 28 October 2026

Trained on the user's Colab Tesla T4 for 12 epochs; validation selected epoch 9.
The 145 held-out images produced 122 correct predictions: **84.14% accuracy**
and **0.8301 macro F1**. The frozen ImageNet centroid baseline achieved 75.17%
accuracy, so the measured aggregate difference is +8.97 percentage points.
Per-class recall was GPU 52.17%, motherboard 91.07%, RAM 85.11%, SSD 100%
(the SSD test has only 19 images from a limited academic collection). GPU recall
fell from the baseline's 82.61%; the aggregate gain does not mean every class
improved. The classifier is suitable here as an experimental advisory, with more
GPU diversity and independently collected unit-disjoint test images needed
before using it to enforce product identity.

The actual export was installed locally, and its ONNX predictions matched the
Colab predictions for all 145 test examples. All three running services reported
healthy with the classifier loaded in Node 3. The 104 software regression tests
passed; these tests do not establish damage recognition accuracy. Versioned
metrics and the confusion matrix are in `results/2026-10-28/`.
