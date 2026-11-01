# Models

`haybale-models:editor:ModelsEditor` · kind: editor

Model files on this machine and where they come from

## Details

- **default_slot**: `action`
- **opens**: `OpenBehavior.REQUIRED`
- **order**: `100`

## Notes

Lists the catalog, the local model files and the Hugging Face cache, with disk usage.

Each catalog resource shows its status: `local`, `HF cache`, `downloading`, `failed` or
`not downloaded`. Download, Cancel and Remove need admin access; a removal names the open
graphs that use the file and the bytes it frees. Opening the editor and **Rescan** index
the files in the models volume on a background thread. When the notice of a graph sent you
here, only the resources that graph needs are listed, and **Fetch all** downloads them.
The Hugging Face cache is read-only: **Reveal location** shows where it lives.
