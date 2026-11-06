# Models

`haybale-models:editor:ModelsEditor` · kind: editor

Model files on this machine and where they come from

## Details

- **default_slot**: `action`
- **opens**: `OpenBehavior.REQUIRED`
- **order**: `100`

## Notes

Lists the model catalog, the files in the Models volume and the Hugging Face files in use.

The **Filters** icon in the header opens the filter section. Its **Show:** row picks the sections
(**Catalog**, **Models**, **Huggingface**). Its search toggle opens a field that narrows every
section: each word must appear, in any order, and scale, licence and `commercial` count too. Its
**+** adds a filter on library, purpose, tags, architecture, scale, commercial use or status, which
narrows the catalog. Closing it switches them all off, so a closed section always means the full
list, and reopening it brings them back.
The **Needed** section is always shown: per open graph, the models it lacks; **Fetch all**
downloads them. Each section header counts what the section lists; hover it for the whole
volume's size.

A catalog row reads `non-commercial` unless its author states the model may be used commercially.
Each catalog resource shows its status: `local`, `HF cache`, `downloading`, `failed` or
`not downloaded`. **Models** lists the files in the Models volume that no catalog entry
occupies. **Huggingface** lists the cached files that catalog entries or open graphs use,
and what uses each; the Volumes editor shows where the cache lives. Download, Cancel and
Remove need admin access; a removal names the open graphs that use the file and the bytes
it frees. Cancel is offered only while a download can still be stopped: a Hugging Face
download, once started, runs to the end. Opening the editor and **Rescan** index the Models
volume on a background thread.
