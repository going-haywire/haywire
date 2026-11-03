# ModelRefWidget

`haybale-models:widget:ModelRefWidget` · kind: widget

Pick a model

## Details

- **min_width**: `220`

## Notes

Pick the model a node uses.

The card shows one line: a state icon, the model's name and an edit button.

- Green icon: the model is on this machine.
- Amber `online_prediction` icon: an address that is not pinned yet; the pin
  button next to it records the digest of the file on this machine.
- Amber icon: the model is not on this machine; fetch it in the Models editor.
- Red icon: no model chosen.

Hover the name for the details. The edit button opens the picker, with the
choice at the top and four tabs:

- **Catalog**: the catalog entries this port accepts. A catalog entry follows
  the catalog: each machine uses the variant that suits it best.
- **Models Volume**: a file in the Models volume, named by its sha256: one you
  put there or fetched by address. Catalog variants are in the Catalog tab.
- **Hugging Face**: a model file in the Hugging Face cache, named by its `hf://`
  address and its sha256, so it works offline.
- **Address**: an `hf://` or `https://` address. An `hf://` address is pinned when
  the Hub answers; an `https://` address once the file is on this machine.

**Use** stores the choice (pinned when its digest is known), **Cancel** drops it.
The picker never downloads: missing models are fetched in the Models editor.

Options (in `properties`):

- `filter`: catalog field to allowed values, such as `{"architecture": ["esrgan"]}`;
  only matching entries are listed.
- `unavailable`: when set, the edit button is unavailable and this text is its
  tooltip, for a node that cannot take a model yet. A node that learns later which
  models fit sets `filter` and drops `unavailable` by rebuilding the port in `rejig`.
- `prefer`: ordered list of tag sets for choosing a variant, such as
  `[{"precision": "fp16"}, {}]`.

```python
MODEL_REF.as_inlet("model", widget_config={"properties": {"filter": {"scale": [4]}}})
```
