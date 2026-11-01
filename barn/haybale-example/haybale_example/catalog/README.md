# Demo model catalog

Each `.json` file here is one model catalog entry, registered as
`haybale-example:model:<file name without .json>`.

- `2x-Compact-Pretrain.json`, `4x-Compact-Pretrain.json`: copied verbatim from the
  [OpenModelDB data repository](https://github.com/OpenModelDB/open-model-database),
  `data/models/`, at commit `782aac088bd83dd3fc438a42eb0c3868dc559110`, on 2026-10-31.
  License of the models: WTFPL.
- `1x-BroadcastToStudio-Compact-onnx.json`: written by hand in the OpenModelDB shape,
  after OpenModelDB's `1x-BroadcastToStudio-Compact.json`. Its two resources are the
  fp32 and fp16 ONNX files of the
  [Kim2091-Models release](https://github.com/Kim2091/Kim2091-Models/releases/tag/1x-BroadcastToStudio_Compact),
  tagged `precision: fp32` / `fp16`. Both sha256 digests were computed from the
  downloaded files on 2026-10-31. License of the model: CC-BY-NC-SA-4.0.
