# ModelRefWidget

`haybale-models:widget:ModelRefWidget` · kind: widget

Pick a model

## Details

- **min_width**: `220`

## Notes

Pick a model from the catalog, or name a file.

The list shows the catalog entries the port accepts, by library, each with
whether it is on this machine (`local`, `HF cache` or `not downloaded`) and
its size. A catalog entry follows the catalog: an update to the entry
reaches every graph that uses it.

Choose **Other…** to name one file instead: type its address (`hf://org/repo/file`
or `https://…`) and press Enter, or browse the Models and Hugging Face cache
folders. A file picked from a folder is named by its sha256. An address
without a digest works, but the card says **not pinned**; **Pin digest** records
the digest of the file on this machine so the graph always gets exactly that
file. For an `hf://` address the digest is asked from the Hub once, when the
address is entered.

The line below says what the reference resolves to, or what is wrong. The
picker never downloads: missing models are fetched in the Models editor.

Options (in `properties`):

- `filter`: catalog field to allowed values, such as `{"architecture": ["esrgan"]}`;
  only matching entries are listed.
- `prefer`: ordered list of tag sets for choosing a variant, such as
  `[{"precision": "fp16"}, {}]`.

```python
MODEL_REF.as_inlet("model", widget_config={"properties": {"filter": {"scale": [4]}}})
```
