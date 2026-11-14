"""models_list / models_needs / models_fetch."""

from __future__ import annotations

from typing import Any

from haywire.core.access import AccessTier
from haywire.core.farmhand import (
    Farmhand,
    FarmhandContext,
    FarmhandError,
    ToolAnnotations,
    farmhand,
)

from haybale_graph_editor.states.graph_app_state import GraphAppState
from haybale_models.matcher import candidates
from haybale_models.needs import NeedsReport, collect_needs, job_matches
from haybale_models.resolver import (
    FetchSpec,
    addresses_of,
    locate_resource,
    place_of,
    resolve,
    unserved_cache,
)
from haybale_models.download import DownloadJob
from haybale_models.states.models_state import ModelsState
from haybale_models.status import resource_status
from haybale_models.value.model_ref import ModelRef


def _models(ctx: FarmhandContext) -> ModelsState:
    return ctx.state(ModelsState)


def _report(ctx: FarmhandContext, binding_id: str) -> NeedsReport:
    """Walk the open graph *binding_id*; unknown binding raises ``graph_not_open``."""
    container = ctx.state(GraphAppState).get(binding_id)
    graph = container.editor.graph if container is not None else None
    if graph is None:
        raise FarmhandError(
            "graph_not_open",
            f"No open graph '{binding_id}'.",
            ids={"binding_id": binding_id},
            help="Call haystack_list_graphs to see the open graphs and their binding_id.",
        )
    models = _models(ctx)

    def resolve_fn(ref: ModelRef, preference: Any) -> Any:
        return resolve(ref, preference, catalog=models.catalog, index=models.index, sources=models.sources)

    return collect_needs(graph, resolve_fn)


def _job_row(models: ModelsState, job: DownloadJob) -> dict[str, Any]:
    """Return the report of one download job; a job the user can finish says so."""
    row: dict[str, Any] = {
        "id": job.id,
        "label": job.label,
        "state": job.state,
        "done_bytes": job.done_bytes,
        "total_bytes": job.total_bytes,
        "error": job.error,
    }
    if models.queue.assistable(job.id):
        row["assisted"] = True
        row["page_urls"] = [url for a in job.sources if (url := models.sources.page_url(a)) is not None]
    return row


@farmhand(
    label="List models",
    description="Catalog entries with per-variant status, indexed local files and download jobs.",
    instructions="Lists the model catalog (every entry with each variant's size and status: local, "
    "HF cache, queued, downloading N %, failed, not downloaded), the files indexed in the models "
    "volume, and the download jobs. detail=true adds license, commercial and description to catalog rows.",
    registry_id="list",
    annotations=ToolAnnotations(read_only_hint=True),
    requires=AccessTier.VIEW,
)
class ModelsListTool(Farmhand):
    """Lists the model catalog, the local model files and the download jobs.

    Returns every catalog entry with its variants (size and status: local, HF cache,
    queued, downloading, failed or not downloaded), every file indexed in the models
    volume, and every download job with its progress. Call it first, to learn the
    catalog keys that `models_fetch` takes and to follow a download. Pass
    `detail=true` to add license, commercial (whether the author states the model may be used
    commercially) and description to the catalog rows.

    A failed job with `assisted` true can be finished by the user: they get the file from one of its
    `page_urls` and hand it over with Download in browser in the Models editor.
    """

    async def run(self, ctx: FarmhandContext, detail: bool = False) -> dict:
        models = _models(ctx)
        jobs = models.queue.jobs()
        catalog: list[dict[str, Any]] = []
        for entry in models.catalog.entries():
            variants = []
            for resource in entry.resources:
                found = locate_resource(resource, models.index, models.sources)
                place = None if found is None else place_of(found[0].values(), models.sources)
                matching = [j for j in jobs if job_matches(j, FetchSpec(entry=entry, resource=resource))]
                variants.append(
                    {
                        "variant": resource.variant_name(),
                        "size": resource.total_size,
                        "status": resource_status(
                            place,
                            matching,
                            unavailable=unserved_cache(resource, models.sources)
                            or models.sources.unavailable(addresses_of(resource)),
                        ),
                    }
                )
            row: dict[str, Any] = {
                "key": entry.class_identity.registry_key,
                "name": entry.name,
                "variants": variants,
            }
            if detail:
                row["license"] = entry.license
                row["commercial"] = entry.commercial
                row["description"] = entry.description
            catalog.append(row)
        local = [
            {"relative": r.relative, "size": r.size, "sha256": r.sha256} for r in models.index.records()
        ]
        job_rows = [_job_row(models, j) for j in jobs]
        return {
            "summary": f"{len(catalog)} catalog entries, {len(local)} local files, {len(job_rows)} jobs.",
            "catalog": catalog,
            "local": local,
            "jobs": job_rows,
            "help": "Run models_fetch keys=[<key>] to download a catalog entry (admin). A job with "
            "assisted=true failed but can be finished by the user: send them to Download in browser in "
            "the Models editor, with its page_urls.",
        }


@farmhand(
    label="Models a graph needs",
    description="The models an open graph references and does not have locally.",
    instructions="Returns the missing models of an open graph, interiors included: label, size "
    "(null when unknown) and the node_ids that ask for it. Get binding_id from haystack_list_graphs.",
    registry_id="needs",
    annotations=ToolAnnotations(read_only_hint=True),
    requires=AccessTier.VIEW,
)
class ModelsNeedsTool(Farmhand):
    """Lists the models an open graph needs and this machine does not have.

    Returns, for the graph under `binding_id`, each missing model with its label, size
    (`null` when unknown) and the ids of the nodes that ask for it, interiors of
    subgraphs and macros included, plus the known total in bytes. Call it before
    starting a graph, or to decide what `models_fetch` should download. Get
    `binding_id` from `haystack_list_graphs`.
    """

    async def run(self, ctx: FarmhandContext, binding_id: str) -> dict:
        report = _report(ctx, binding_id)
        rows = [{"label": m.label, "size": m.size, "node_ids": list(m.node_ids)} for m in report.missing]
        result: dict[str, Any] = {
            "summary": f"{len(rows)} missing models ({report.total_bytes} bytes known, "
            f"{report.unknown_size} of unknown size).",
            "missing": rows,
            "total_bytes": report.total_bytes,
            "unknown_size": report.unknown_size,
        }
        if rows:
            result["help"] = f"Run models_fetch binding_id={binding_id!r} to download them (admin)."
        return result


@farmhand(
    label="Fetch models",
    description="Queue downloads: everything an open graph needs, or catalog entries by key (admin).",
    instructions="Queues the downloads and returns their job ids; progress is in models_list jobs. "
    "Pass binding_id to fetch everything that graph needs, or keys=[<catalog key>, ...] to fetch "
    "the preferred variant of each entry. Needs admin access.",
    registry_id="fetch",
    annotations=ToolAnnotations(open_world_hint=True),
    requires=AccessTier.ADMIN,
)
class ModelsFetchTool(Farmhand):
    """Queues downloads of missing models. Needs ADMIN access.

    Pass `binding_id` to fetch everything that open graph needs, or `keys` to fetch the
    preferred variant of each catalog entry. Returns the job ids at once; the files
    arrive in the background, so call `models_list` to follow the jobs. Downloads use
    network and disk: call it only when the user wants the models.
    """

    async def run(
        self, ctx: FarmhandContext, binding_id: str | None = None, keys: list[str] | None = None
    ) -> dict:
        if binding_id is None and not keys:
            raise FarmhandError(
                "nothing_to_fetch",
                "Pass binding_id or keys.",
                help="Run models_needs binding_id=<id> for a graph, or models_list for catalog keys.",
            )
        models = _models(ctx)
        specs: list[FetchSpec] = []
        if binding_id is not None:
            specs.extend(m.spec for m in _report(ctx, binding_id).missing)
        for key in keys or []:
            entry = models.catalog.entry(key)
            ranked = candidates(entry.resources, [{}]) if entry is not None else []
            if entry is None or not ranked:
                raise FarmhandError(
                    "unknown_model",
                    f"No catalog entry '{key}'.",
                    ids={"key": key},
                    help="Run models_list to see the catalog keys.",
                )
            specs.append(FetchSpec(entry=entry, resource=ranked[0][1]))
        job_ids = models.fetch(specs, ctx.principal)
        return {
            "summary": f"Queued {len(job_ids)} downloads.",
            "job_ids": job_ids,
            "help": "Run models_list to follow the jobs.",
        }
