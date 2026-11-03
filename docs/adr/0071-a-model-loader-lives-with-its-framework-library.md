---
name: a-model-loader-lives-with-its-framework-library
description: A framework library owns its model loader, its loaded-model types and its Load node; haybale-models owns model files, the catalog, the picker and the loaded-models pool. A loader's outlet takes its model kind from the first inlet it is connected to, and the picker offers only that kind
status: accepted
see-also: ADR-0067, ADR-0068, ADR-0070
level: library
---

# A model loader lives with its framework library

**Context.**

- haybale-models (S6) knows where model files are: catalog entries and their variants, the Models volume, the Hugging Face cache, digests, fetching. It also holds the loaded-models pool, which shares one loaded copy between nodes and frees it when no node holds it.
- Turning a file into something that runs is framework business: spandrel needs a device, a precision, `ModelLoader` and its descriptors; a ComfyUI-like or ONNX library would need something else entirely.
- Each framework has several kinds of model that are not interchangeable: spandrel has image-to-image models (super-resolution, restoration) and inpainting models. With one loaded-model type, a user had to know which catalog entry fits which consumer, and a wrong pick showed up only when the graph ran.

**Decision.**

- **Split by responsibility.** haybale-models owns files, catalog, the `MODEL_REF` picker and the pool. A framework library owns its loader function, its loaded-model types and its Load node, which holds its model in the pool (`pool.acquire(key, holder, load, release)`) and releases it when the run stops. haybale-models imports no framework.
- **Loaded-model kinds are types.** A framework declares a base type and one subtype per kind a consumer can run (`MODEL_BASE`; `IMAGE_MODEL`, `INPAINT_MODEL`). Each kind declares its catalog filter (`catalog_filter`) and which loaded models fit it (`fits`). A consumer's inlet names the kind it runs; an inlet that takes any kind names the base.
- **The loader's outlet takes its kind from what it feeds.** The Load node's outlet starts as a bare `ADD`. Connecting it to an inlet of a kind retypes the outlet to that kind; any other inlet makes it the base type, whose edge is then invalid. The outlet keeps its kind until the node is reset. Undo of the connection does not release it (`BaseNode.release_pins` releases nothing by default).
- **The picker follows the kind.** The Load node has no model inlet until its outlet has a kind; the connect handler adds it, with the kind's `catalog_filter` as the picker's `filter`. The filter lives on the port, so save, copy and undo carry it with the outlet.
- **A wrong kind is caught twice.** The type check refuses the wiring (an invalid edge); a file picked outside the catalog is checked after loading with the kind's `fits`.

**Considered.**

- *haybale-models provides the loaders.* It would import every framework and grow with each one, and a framework library could not ship a new kind without changing it.
- *Name catalog entries by use case.* Cheap, but drifts from OpenModelDB's names and does not stop a wrong pick.
- *A Purpose setting on the Load node.* The user would still have to know which purpose the consumer needs.
- *The picker reads the consumers' declared filters along the outlet's edges.* No type check, and following edges through Reroute nodes and Group boundaries is code of its own; the wiring would also change the filter silently.
- *A callback edge from the consumer back to the loader carrying the requirement.* A second wire between every pair, easy to forget.
- *A node hook (`model_filter`) the picker asks.* Correct, but the picker had to reach the node through the widget model; the filter on the port is simpler and is saved with it.
- *One growing outlet per kind.* One model can serve only one kind; a second outlet of another kind could never be satisfied.

**Consequences.**

- A new framework library ships a loader, kinds and a Load node, and gets files, catalog, picker and pool for free.
- A fresh Load node shows only its outlet; the picker appears when it is connected, filtered to entries of that kind. Catalog entries must declare `purpose` for a filter on it to match them.
- Retyping a port from `on_connect` while a new edge links needed a core fix: the edge's adapter chain is now rebuilt on the next validation pass when its ports changed since it was built (`EdgeWrapper.built_for_current_ports`).
- A Load node changes kind only through reset.
