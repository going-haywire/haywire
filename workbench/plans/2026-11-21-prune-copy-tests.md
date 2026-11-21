# Prune tests that pin hand-written copy

Date: 2026-11-21 · Branch: `test/prune-copy-tests` · Tests only, no product code.

## Rule

- **delete**: the test's only assertion is a fixed, hand-set informational string (description,
  tooltip, placeholder, hint or empty-state copy, dialog wording, menu or panel label spelling)
  or a restated default value with no behaviour behind it.
- **trim**: the test also checks real behaviour; the copy assertion is dropped or loosened to the
  dynamic piece (the node name, the count, the size), to "non-empty", or to the product's own
  constant.
- **keep**: the test checks that computed or received text is displayed, the text is a locator for
  a behaviour assertion, or the copy is defined by the test fixture itself (plumbing).
- **grey**: copy that is a contract (agent-facing text, generated docs format, a command the user
  must type), a load-bearing default, or an exception/validation message that tells which check
  fired. Not touched; decisions below.
- **reverted**: the sweep first trimmed it (almost all are `pytest.raises(match=…)` or
  `assert "…" in err` on validation errors); restored because the message identifies which rule
  fired, which is behaviour, and error messages are not on the delete list. Grouped as decision G0.

## Counts

| Category | Rows |
|---|---|
| delete | 16 (whole tests) |
| trim | 104 |
| reverted → grey G0 | 124 |
| grey | 24 (grouped into G1–G5) |
| keep | 135 (plus 7 multi-file keep rows below) |

A row can cover several asserts in one test; line numbers are those of `master` at 1b9c74674.

## Decisions for the user

**G0 — exception and validation messages (124 rows, reverted).** `match="cannot be promoted"`,
`assert "only outlets" in err`, `match="Illegal cycle detected"` …
a) keep as they are; b) loosen each to its dynamic piece or a key word; c) drop to the exception
type only (ruff PT011 forbids a bare `pytest.raises(ValueError)`, so ValueError cases need b).
**Recommend a**: the phrase is what tells one refusal from another of the same exception type;
dropping it lets a test pass on the wrong failure.

**G1 — load-bearing defaults.** `size_adapt == "auto"`, flow meters on, graph `autorestart`
False (duplicate line in `test_graph_entry.py:174`), bail policy `"branch"`, Farmhand audit
`log_path == ""` (off), torch backend `"auto"`.
a) keep all; b) delete as restated defaults; c) keep all, drop only the duplicate autorestart
line in `test_graph_entry.py`. **Recommend c**: each default changes behaviour nothing else
catches; the duplicate adds nothing.

**G2 — text that names a command or API the user must use.** `UiState.HIDDEN` hint in
`test_field_name_guard.py:38`, `match="ssl setup"` in `test_tls_operations.py:128`, relaunch
command `uv run haywire` (restart affordance, update check/confirm).
a) keep; b) delete/loosen. **Recommend a**: a stale command name misleads the user, and these
change only with the API.

**G3 — agent-facing text.** Farmhand refusal "needs edit access"
(`graph_editor_tools.py:1411`), baseline hint "narrow this" (`baseline_tools.py:143/153`), model
tool help "Download in browser" (`test_model_tools.py:266`), share CLI / human-steps / agent
playbook sentences, session-hook instructions in `tests/scripts/test_claude_hooks.py`.
a) keep all; b) drop the two Farmhand prose lines (keep the tool name and `count_only=true`
checks), keep the rest. **Recommend a** for now; b is safe if those two hints get reworded.

**G4 — wording that is the only branch signal.** Haystack remove dialog
(`test_haystack_editor_remove.py:113/146/161`): "stays on disk" / "unsaved changes" / "never been
saved" tell three branches apart that share `confirm_label`.
a) keep; b) trim to `confirm_label` (loses the distinction); c) product exposes a branch key
(out of scope here). **Recommend a**, c if the wording churns.

**G5 — deliberate wording requirements.** `tests/test_ssl_cli.py` says in its docstring that the
printed wording is the requirement; generated README labels "Always the latest" / "Frozen to this
version" (`test_share_readme_markers.py:274`).
a) keep; b) apply the copy rule. **Recommend a.**

## Commits

One commit per area so a group can be reverted alone: core, ui, graph editor + haystack + studio
+ farmhand, libraries + CLI.

## Inventory

### core

| Where | Test | Category | Reason |
|---|---|---|---|
| [tests/core/settings/test_node_size_props.py:17](../../tests/core/settings/test_node_size_props.py#L17) | test_size_defaults_are_200 | delete | restates width/height default 200 |
| [tests/core/test_macro/test_promote_swap.py:279](../../tests/core/test_macro/test_promote_swap.py#L279) | test_the_default_undo_description_is_save_new_macro | delete | only asserts fallback undo label "Save new Macro" |
| [tests/core/test_tooling_settings.py:8](../../tests/core/test_tooling_settings.py#L8) | test_external_editor_command_default | delete | restates default `"code --goto {file}:{line}"`; file held only this test, file removed |
| [tests/core/test_undo/test_undo_settings.py:8](../../tests/core/test_undo/test_undo_settings.py#L8) | test_max_actions_default | delete | restates default 100; wiring kept by test_undo_config_defaults_to_the_setting |
| [tests/core/signals/test_editor_command.py:71](../../tests/core/signals/test_editor_command.py#L71) | test_toggle_lock_identity | trim | dropped menu label "Lock / Unlock"; command_id, keys, tier kept |
| [tests/core/signals/test_editor_command.py:81](../../tests/core/signals/test_editor_command.py#L81) | test_toggle_stage_view_identity | trim | dropped menu label "Patch / Stage" |
| [tests/core/test_errors/test_extract.py:24](../../tests/core/test_errors/test_extract.py#L24) | test_a_failing_lambda_is_named_not_its_enclosing_def | trim | exact suggestion sentence to a suggestion naming `<lambda>` and the line number |
| [tests/core/test_errors/test_extract.py:34](../../tests/core/test_errors/test_extract.py#L34) | test_a_failing_def_is_still_named | trim | exact suggestion sentence to a suggestion naming 'on_click' |
| [tests/core/test_graph/test_graph_identity_metadata.py:128](../../tests/core/test_graph/test_graph_identity_metadata.py#L128) | test_meta_defaults | trim | dropped version "1.0.0" default; empty label/description/author kept |
| [tests/core/test_graph/test_load_save_boundary.py:62](../../tests/core/test_graph/test_load_save_boundary.py#L62) | test_unreadable_file_is_recorded | trim | "Could not load graph '...'" to filename-in-message |
| [tests/core/test_graph/test_load_save_boundary.py:148](../../tests/core/test_graph/test_load_save_boundary.py#L148) | (reopen previous-setup test) | trim | "holds a previous setup" to node_id-in-message |
| [tests/core/test_node/test_annotation_node.py:341](../../tests/core/test_node/test_annotation_node.py#L341) | test_the_annotation_bag_holds_text_and_arrangement_with_defaults | trim | cosmetic defaults center/middle/sans/14 loosened to "set"; empty text, no-style, no-colour kept |
| [tests/core/test_node/test_fold.py:162](../../tests/core/test_node/test_fold.py#L162) | test_a_fold_describes_itself_without_the_author | trim | FOLD type blurb literal replaced by `== FOLD.class_identity.description`, non-empty, `!= BOOL` description; explicit description= line (fixture copy) kept |
| [tests/core/test_node/test_previous_setup.py:99](../../tests/core/test_node/test_previous_setup.py#L99) | test_report_names_the_node_in_a_root_graph | trim | full f-string equality to display_label and node_id in message |
| [tests/core/test_node/test_previous_setup.py:123](../../tests/core/test_node/test_previous_setup.py#L123) | test_report_names_the_host_of_an_interior | trim | endswith prose to host label in message |
| [tests/core/test_node/test_stage_model.py:47](../../tests/core/test_node/test_stage_model.py#L47) | test_stage_props_defaults | trim | dropped stage size 200x200 default; on_stage False, origin, size_adapt kept |
| [tests/core/test_undo/test_history_snapshot.py:153](../../tests/core/test_undo/test_history_snapshot.py#L153) | test_a_flushed_group_lists_its_children_with_their_own_origins | trim | "Group of 2 actions" to the computed count "2" in description |
| [tests/core/node/test_boundary_nodes.py:232](../../tests/core/node/test_boundary_nodes.py#L232) | test_subgraph_input_with_an_inlet_fails_with_a_named_reason | reverted | dropped "only outlets"; port name "value" in err kept |
| [tests/core/node/test_boundary_nodes.py:245](../../tests/core/node/test_boundary_nodes.py#L245) | test_subgraph_output_with_an_outlet_fails_with_a_named_reason | reverted | dropped "only inlets"; port name kept |
| [tests/core/node/test_boundary_nodes.py:304](../../tests/core/node/test_boundary_nodes.py#L304) | test_a_subgraph_with_two_inputs_fails | reverted | "exactly one" to non-empty err |
| [tests/core/node/test_boundary_nodes.py:315](../../tests/core/node/test_boundary_nodes.py#L315) | test_a_subgraph_missing_its_output_fails | reverted | "exactly one" to non-empty err |
| [tests/core/node/test_boundary_nodes.py:325](../../tests/core/node/test_boundary_nodes.py#L325) | test_a_subgraph_containing_an_event_node_fails | reverted | dropped "EVENT or OUTPUT"; node label "Begin Play" kept |
| [tests/core/node/test_boundary_nodes.py:337](../../tests/core/node/test_boundary_nodes.py#L337) | test_a_subgraph_containing_an_output_node_fails | reverted | dropped "EVENT or OUTPUT"; node label kept |
| [tests/core/node/test_promotion_single_cell.py:74](../../tests/core/node/test_promotion_single_cell.py#L74) | test_watch_default_direction_rejected_shadow_default_ok | reverted | fixed message match "cannot be promoted to inlet" loosened to dynamic/identifier part "inlet" |
| [tests/core/node/test_promotion_single_cell.py:243](../../tests/core/node/test_promotion_single_cell.py#L243) | test_watch_to_inlet_rejected_watch_to_outlet_ok | reverted | fixed message match "cannot be promoted to inlet" loosened to dynamic/identifier part "inlet" |
| [tests/core/settings/test_promotable_eligibility.py:108](../../tests/core/settings/test_promotable_eligibility.py#L108) | test_promote_none_field_raises | reverted | fixed message match "cannot be promoted" dropped; exception type kept |
| [tests/core/settings/test_promotable_eligibility.py:119](../../tests/core/settings/test_promotable_eligibility.py#L119) | test_promote_outlet_only_field_to_inlet_raises | reverted | fixed message match "cannot be promoted" dropped; exception type kept |
| [tests/core/settings/test_promotable_eligibility.py:129](../../tests/core/settings/test_promotable_eligibility.py#L129) | test_promote_config_only_field_to_inlet_raises | reverted | fixed message match "cannot be promoted" dropped; exception type kept |
| [tests/core/settings/test_promote_demote_bag_api.py:66](../../tests/core/settings/test_promote_demote_bag_api.py#L66) | test_bag_promote_raises_for_ineligible_direction | reverted | fixed message match "cannot be promoted" dropped; exception type kept |
| [tests/core/signals/test_keys.py:22](../../tests/core/signals/test_keys.py#L22) | test_normalize_keeps_named_key_spelling | reverted | fixed message match "key combo" loosened to dynamic/identifier part re.escape(repr(bad)) |
| [tests/core/signals/test_keys.py:58](../../tests/core/signals/test_keys.py#L58) | test_normalize_named_key_is_case_insensitive | reverted | fixed message match "key combo" loosened to dynamic/identifier part re.escape(repr(bad)) |
| [tests/core/test_assembly/test_flat_view.py:529](../../tests/core/test_assembly/test_flat_view.py#L529) | test_an_unbound_card_aborts_the_assembly | reverted | fixed message match "no Subgraph is bound" dropped; exception type kept |
| [tests/core/test_assembly/test_flat_view.py:569](../../tests/core/test_assembly/test_flat_view.py#L569) | test_an_event_node_inside_a_subgraph_is_refused | reverted | fixed message match "EVENT or OUTPUT" dropped; exception type kept |
| [tests/core/test_assembly/test_flat_view.py:578](../../tests/core/test_assembly/test_flat_view.py#L578) | test_a_missing_boundary_node_is_refused | reverted | fixed message match "exactly one Subgraph Input" dropped; exception type kept |
| [tests/core/test_assembly/test_flat_view.py:588](../../tests/core/test_assembly/test_flat_view.py#L588) | test_two_cards_bound_to_one_subgraph_are_refused | reverted | fixed message match "bound by 2 Graph-nodes" loosened to dynamic/identifier part r"\b2\b" |
| [tests/core/test_assembly/test_swinglet_assembly.py:117](../../tests/core/test_assembly/test_swinglet_assembly.py#L117) | test_a_data_cycle_is_refused_at_assembly | reverted | fixed message match "Illegal cycle detected in data flow" dropped; exception type kept |
| [tests/core/test_authoring/test_write_node.py:72](../../tests/core/test_authoring/test_write_node.py#L72) | test_a_refused_plan_is_never_written | reverted | fixed message match "cannot be written" loosened to dynamic/identifier part re.escape(str(plan.refusal)) |
| [tests/core/test_authoring/test_write_node.py:243](../../tests/core/test_authoring/test_write_node.py#L243) | test_a_watch_needs_something_to_match | reverted | fixed message match "needs a module_name" loosened to dynamic/identifier part "module_name" |
| [tests/core/test_catalog/test_catalog_registry.py:191](../../tests/core/test_catalog/test_catalog_registry.py#L191) | test_cache_without_address_is_refused | reverted | fixed message match "cache must be an address" loosened to dynamic/identifier part "cache" |
| [tests/core/test_catalog/test_catalog_registry.py:238](../../tests/core/test_catalog/test_catalog_registry.py#L238) | test_include_not_a_list_of_strings_is_refused | reverted | fixed message match "include must be a list" loosened to dynamic/identifier part "include" |
| [tests/core/test_di/test_library_state_container_global.py:22](../../tests/core/test_di/test_library_state_container_global.py#L22) | test_get_raises_before_set | reverted | fixed message match "LibraryStateContainer not set" loosened to dynamic/identifier part "LibraryStateContainer" |
| [tests/core/test_di/test_session_manager_global.py:16](../../tests/core/test_di/test_session_manager_global.py#L16) | test_get_raises_before_set | reverted | fixed message match "SessionManager not set" loosened to dynamic/identifier part "SessionManager" |
| [tests/core/test_di/test_workspace_root_global.py:15](../../tests/core/test_di/test_workspace_root_global.py#L15) | test_get_raises_before_set | reverted | fixed message match "workspace_root not set" loosened to dynamic/identifier part "workspace_root" |
| [tests/core/test_edge/test_drain_inlet_edge.py:71](../../tests/core/test_edge/test_drain_inlet_edge.py#L71) | test_an_ordinary_field_refuses_take | reverted | fixed message match "does not queue values" dropped; exception type kept |
| [tests/core/test_edge/test_drain_inlet_edge.py:149](../../tests/core/test_edge/test_drain_inlet_edge.py#L149) | test_fails_validation | reverted | dropped "needs every value"; error_formal present kept |
| [tests/core/test_edge/test_edge_propagation.py:158](../../tests/core/test_edge/test_edge_propagation.py#L158) | test_a_callback_edge_refuses_a_choice | reverted | fixed message match "cannot take" loosened to dynamic/identifier part Propagation.LAZY.value |
| [tests/core/test_edge/test_swinglet_links.py:94](../../tests/core/test_edge/test_swinglet_links.py#L94) | test_a_reverse_visual_edge_is_refused | reverted | fixed message match "other way" dropped; exception type kept |
| [tests/core/test_edge/test_swinglet_links.py:101](../../tests/core/test_edge/test_swinglet_links.py#L101) | test_a_reverse_control_edge_is_refused_too | reverted | fixed message match "other way" dropped; exception type kept |
| [tests/core/test_execution/test_array_loops.py:149](../../tests/core/test_execution/test_array_loops.py#L149) | test_list_files_missing_folder_raises | reverted | fixed message match "does not exist" dropped; exception type kept |
| [tests/core/test_graph/test_annotation_links.py:59](../../tests/core/test_graph/test_annotation_links.py#L59) | test_a_reverse_note_link_is_refused | reverted | fixed message match "other way" dropped; exception type kept |
| [tests/core/test_graph/test_arrange.py:290](../../tests/core/test_graph/test_arrange.py#L290) | test_directed_scopes_refuse_several_start_nodes | reverted | fixed message match "one start node" loosened to dynamic/identifier part r"\\b2\\b" |
| [tests/core/test_graph/test_graph_node.py:501](../../tests/core/test_graph/test_graph_node.py#L501) | test_an_unbound_card_is_invalid | reverted | dropped "no Subgraph bound"; not ok + message present kept |
| [tests/core/test_graph/test_prehydration.py:170](../../tests/core/test_graph/test_prehydration.py#L170) | test_future_version_is_refused | reverted | fixed message match "newer Haywire" dropped; exception type kept |
| [tests/core/test_graph/test_prehydration.py:175](../../tests/core/test_graph/test_prehydration.py#L175) | test_non_graph_is_refused | reverted | fixed message match "not a recognisable" dropped; exception type kept |
| [tests/core/test_graph/test_prehydration.py:186](../../tests/core/test_graph/test_prehydration.py#L186) | test_non_graph_lacking_legacy_keys_is_still_refused | reverted | fixed message match "not a recognisable" dropped; exception type kept |
| [tests/core/test_libraries/test_library_root_folder_guard.py:60](../../tests/core/test_libraries/test_library_root_folder_guard.py#L60) | test_registering_the_library_root_raises | reverted | fixed message match "cannot register the library root" loosened to dynamic/identifier part "_Registry" |
| [tests/core/test_libraries/test_library_root_folder_guard.py:68](../../tests/core/test_libraries/test_library_root_folder_guard.py#L68) | test_the_root_is_recognised_through_a_non_normalised_path | reverted | fixed message match "cannot register the library root" loosened to dynamic/identifier part "_Registry" |
| [tests/core/test_library/test_decorated_before_library.py:62](../../tests/core/test_library/test_decorated_before_library.py#L62) | test_component_imported_above_library_raises | reverted | fixed message match rf"{_PACKAGE}\.probe_state\.ProbeState was decorated before" loosened to dynamic/identifier part rf"{_PACKAGE}\.probe_state\.ProbeState" |
| [tests/core/test_library/test_haybale_toml.py:73](../../tests/core/test_library/test_haybale_toml.py#L73) | test_missing_file_raises | reverted | fixed message match "not found" dropped; exception type kept |
| [tests/core/test_library/test_haybale_toml.py:80](../../tests/core/test_library/test_haybale_toml.py#L80) | test_malformed_toml_raises_with_the_path | reverted | fixed message match "Malformed TOML" dropped; exception type kept |
| [tests/core/test_library/test_haybale_toml.py:87](../../tests/core/test_library/test_haybale_toml.py#L87) | test_missing_name_raises | reverted | fixed message match "`name` is required" loosened to dynamic/identifier part "name" |
| [tests/core/test_library/test_haybale_toml.py:93](../../tests/core/test_library/test_haybale_toml.py#L93) | test_empty_name_raises | reverted | fixed message match "`name` is required" loosened to dynamic/identifier part "name" |
| [tests/core/test_library/test_haybale_toml.py:99](../../tests/core/test_library/test_haybale_toml.py#L99) | test_missing_version_raises | reverted | fixed message match "`version` is required" loosened to dynamic/identifier part "version" |
| [tests/core/test_library/test_haybale_toml.py:105](../../tests/core/test_library/test_haybale_toml.py#L105) | test_empty_version_raises | reverted | fixed message match "`version` is required" loosened to dynamic/identifier part "version" |
| [tests/core/test_library/test_haybale_toml.py:111](../../tests/core/test_library/test_haybale_toml.py#L111) | test_wrong_scalar_type_raises | reverted | fixed message match "label must be a string" loosened to dynamic/identifier part "label" |
| [tests/core/test_library/test_haybale_toml.py:117](../../tests/core/test_library/test_haybale_toml.py#L117) | test_wrong_list_type_raises | reverted | fixed message match "must be a list of strings" loosened to dynamic/identifier part "linked_libraries" |
| [tests/core/test_library/test_haybale_toml.py:130](../../tests/core/test_library/test_haybale_toml.py#L130) | test_non_module_linked_library_raises | reverted | fixed message match "module names" dropped; exception type kept |
| [tests/core/test_macro/test_macro_registry.py:103](../../tests/core/test_macro/test_macro_registry.py#L103) | (containment refusal test) | reverted | dropped "exactly one"; CLASS_RELOAD_FAILED event kept |
| [tests/core/test_macro/test_macro_registry.py:112](../../tests/core/test_macro/test_macro_registry.py#L112) | test_a_macro_containing_an_event_node_is_refused | reverted | "EVENT or OUTPUT" to lastevent carries an error |
| [tests/core/test_macro/test_macro_registry.py:159](../../tests/core/test_macro/test_macro_registry.py#L159) | test_a_self_referencing_macro_is_refused | reverted | "places itself" to lastevent carries an error |
| [tests/core/test_macro/test_promote_plan.py:215](../../tests/core/test_macro/test_promote_plan.py#L215) | test_writing_a_refused_plan_raises | reverted | fixed message match "cannot be saved as a macro" loosened to dynamic/identifier part re.escape(str(plan.refusal)) |
| [tests/core/test_node/test_annotation_node.py:242](../../tests/core/test_node/test_annotation_node.py#L242) | test_a_declared_port_cannot_be_removed | reverted | fixed message match "declared by the node" dropped; exception type kept |
| [tests/core/test_node/test_fold.py:211](../../tests/core/test_node/test_fold.py#L211) | test_mixing_directions_in_one_fold_raises | reverted | dropped "one direction" message check; _build still asserts init failed with ValueError |
| [tests/core/test_node/test_fold.py:219](../../tests/core/test_node/test_fold.py#L219) | test_a_fold_inside_a_fold_raises | reverted | dropped "not other folds" message check |
| [tests/core/test_node/test_fold.py:227](../../tests/core/test_node/test_fold.py#L227) | test_an_empty_fold_raises | reverted | dropped "holds no ports" message check |
| [tests/core/test_node/test_node_props_bag_override.py:45](../../tests/core/test_node/test_node_props_bag_override.py#L45) | test_a_non_subclass_bag_is_still_rejected | reverted | fixed message match "without subclassing it" loosened to dynamic/identifier part "_BadBagNode" |
| [tests/core/test_settings/test_field_name_guard.py:23](../../tests/core/test_settings/test_field_name_guard.py#L23) | test_underscore_prefixed_field_is_rejected_at_class_definition | reverted | fixed message match r"may not start with '_'" loosened to dynamic/identifier part r"_hidden" |
| [tests/core/test_settings/test_field_name_guard.py:47](../../tests/core/test_settings/test_field_name_guard.py#L47) | test_a_field_colliding_with_internal_state_is_rejected | reverted | fixed message match r"may not start with '_'" loosened to dynamic/identifier part r"_set_keys" |
| [tests/core/test_settings/test_graph_settings.py:107](../../tests/core/test_settings/test_graph_settings.py#L107) | test_promotion_unavailable | reverted | fixed message match "bag has no bound node" loosened to dynamic/identifier part "default_skin" |
| [tests/core/test_settings/test_mirror_cell_authoritative.py:152](../../tests/core/test_settings/test_mirror_cell_authoritative.py#L152) | test_same_bag_mirror_raises_value_error | reverted | fixed message match "same bag" loosened to dynamic/identifier part "SameBagBag" |
| [tests/core/test_settings/test_schema_rebasing.py:99](../../tests/core/test_settings/test_schema_rebasing.py#L99) | test_globalSettings_deep_subclass_raises | reverted | fixed message match "Subclassing a FrameworkSettings subclass" loosened to dynamic/identifier part "FrameworkSettings" |
| [tests/core/test_settings/test_schema_rebasing.py:118](../../tests/core/test_settings/test_schema_rebasing.py#L118) | test_librarySettings_deep_subclass_raises | reverted | fixed message match "Subclassing a LibrarySettings subclass" loosened to dynamic/identifier part "LibrarySettings" |
| [tests/core/test_settings/test_settings.py:379](../../tests/core/test_settings/test_settings.py#L379) | test_conflict_raises_at_decoration | reverted | fixed message match "conflicts with" loosened to dynamic/identifier part "_ConflictNode" |
| [tests/core/test_settings/test_settings.py:500](../../tests/core/test_settings/test_settings.py#L500) | test_invalid_default_raises_at_definition_time | reverted | fixed message match "fails validation" loosened to dynamic/identifier part r"\\b3\\b" |
| [tests/core/test_state/test_decorator.py:76](../../tests/core/test_state/test_decorator.py#L76) | test_rejects_non_state_class | reverted | fixed message match "@state can only be applied" loosened to dynamic/identifier part "@state" |
| [tests/core/test_state/test_decorator.py:87](../../tests/core/test_state/test_decorator.py#L87) | test_rejects_bare_library_state_subclass | reverted | fixed message match "@state can only be applied" loosened to dynamic/identifier part "@state" |
| [tests/core/test_state/test_session_state.py:50](../../tests/core/test_state/test_session_state.py#L50) | test_bare_library_settings_field_rejected | reverted | fixed message match "LibrarySettings cannot be composed" loosened to dynamic/identifier part "LibrarySettings" |
| [tests/core/test_state/test_session_state.py:61](../../tests/core/test_state/test_session_state.py#L61) | test_optional_library_settings_field_rejected | reverted | fixed message match "LibrarySettings cannot be composed" loosened to dynamic/identifier part "LibrarySettings" |
| [tests/core/test_state/test_session_state.py:72](../../tests/core/test_state/test_session_state.py#L72) | test_union_library_settings_field_rejected | reverted | fixed message match "LibrarySettings cannot be composed" loosened to dynamic/identifier part "LibrarySettings" |
| [tests/core/test_types/test_add_type.py:91](../../tests/core/test_types/test_add_type.py#L91) | test_it_cannot_grow_another_add | reverted | fixed message match "cannot grow another ADD" loosened to dynamic/identifier part "ADD" |
| [tests/core/test_types/test_add_type.py:95](../../tests/core/test_types/test_add_type.py#L95) | test_a_non_type_is_refused | reverted | fixed message match "not a valid type" dropped; exception type kept |
| [tests/core/test_types/test_add_type.py:317](../../tests/core/test_types/test_add_type.py#L317) | test_two_bare_slots_do_not_link | reverted | dropped "Two bare ADD slots cannot link"; error present + not validated kept |
| [tests/core/test_types/test_container_signal_elements.py:73](../../tests/core/test_types/test_container_signal_elements.py#L73) | test_a_pool_of_exec_stays_refused | reverted | fixed message match "never fired" loosened to dynamic/identifier part "PooledType" |
| [tests/core/test_types/test_drain_type.py:81](../../tests/core/test_types/test_drain_type.py#L81) | test_refuses_a_write_without_a_source | reverted | fixed message match "only from its edge" loosened to dynamic/identifier part "DrainField" |
| [tests/core/test_types/test_drain_type.py:114](../../tests/core/test_types/test_drain_type.py#L114) | test_refuses_a_max_len_below_one | reverted | fixed message match "at least 1" loosened to dynamic/identifier part "max_len" |
| [tests/core/test_types/test_drain_type.py:186](../../tests/core/test_types/test_drain_type.py#L186) | test_refuses_an_outlet | reverted | fixed message match "inlets only" loosened to dynamic/identifier part "DRAIN" |
| [tests/core/test_types/test_drain_type.py:191](../../tests/core/test_types/test_drain_type.py#L191) | test_refuses_an_element_that_carries_no_values | reverted | fixed message match "carries values" loosened to dynamic/identifier part element.__name__ |
| [tests/core/test_types/test_port_id_validation.py:17](../../tests/core/test_types/test_port_id_validation.py#L17) | test_dotted_author_port_id_is_rejected | reverted | fixed message match "reserved for promoted settings" loosened to dynamic/identifier part r"props\\.skin" |
| [tests/core/test_types/test_port_id_validation.py:35](../../tests/core/test_types/test_port_id_validation.py#L35) | test_promoted_flag_is_required_for_the_dotted_form | reverted | fixed message match "reserved for promoted settings" loosened to dynamic/identifier part r"filter\\.strength" |
| [tests/core/test_types/test_swinglet_port.py:61](../../tests/core/test_types/test_swinglet_port.py#L61) | test_a_pooled_type_refuses_a_swinglet | reverted | fixed message match "inlets only" loosened to dynamic/identifier part "PooledType" |
| [tests/core/test_types/test_type_rules.py:12](../../tests/core/test_types/test_type_rules.py#L12) | test_a_value_type_without_a_wire_type_is_refused | reverted | fixed message match "needs a wire type" dropped; exception type kept |
| [tests/core/test_types/test_wire_derivation.py:63](../../tests/core/test_types/test_wire_derivation.py#L63) | test_a_port_spec_refuses_a_wire_type_kwarg | reverted | fixed message match "takes its wire type from its type" dropped; exception type kept |
| [tests/core/test_types/test_wire_derivation.py:69](../../tests/core/test_types/test_wire_derivation.py#L69) | test_a_port_spec_refuses_an_allow_multiple_links_kwarg | reverted | fixed message match "link ceiling.*single_link=True" loosened to dynamic/identifier part "single_link=True" |
| [tests/core/test_types/test_wire_derivation.py:75](../../tests/core/test_types/test_wire_derivation.py#L75) | test_a_port_spec_refuses_a_flow_type_kwarg | reverted | fixed message match "wire type comes from its data type.*wire_type=" loosened to dynamic/identifier part "wire_type=" |
| [tests/core/test_types/test_wrapper_type.py:53](../../tests/core/test_types/test_wrapper_type.py#L53) | test_a_wrapper_may_not_wrap_a_wrapper | reverted | fixed message match "cannot wrap another wrapper" dropped; exception type kept |
| [tests/core/test_types/test_wrapper_type.py:163](../../tests/core/test_types/test_wrapper_type.py#L163) | test_an_element_stored_by_basefield_is_refused | reverted | fixed message match "only defined for PrimitiveField storage" loosened to dynamic/identifier part "PrimitiveField" |
| [tests/core/test_undo/test_collapse_expand.py:364](../../tests/core/test_undo/test_collapse_expand.py#L364) | test_a_refused_collapse_changes_nothing | reverted | fixed message match "cannot be collapsed" dropped; exception type kept |
| [tests/core/test_undo/test_collapse_expand.py:373](../../tests/core/test_undo/test_collapse_expand.py#L373) | test_an_empty_selection_is_refused | reverted | fixed message match "Nothing to collapse" dropped; exception type kept |
| [tests/core/test_undo/test_collapse_expand.py:485](../../tests/core/test_undo/test_collapse_expand.py#L485) | test_expanding_a_plain_node_is_refused | reverted | fixed message match "not a Graph-node" dropped; exception type kept |
| [tests/core/test_undo/test_collapse_expand.py:491](../../tests/core/test_undo/test_collapse_expand.py#L491) | test_expanding_an_unknown_node_is_refused | reverted | fixed message match "not found" dropped; exception type kept |
| [tests/core/test_undo/test_collapse_expand.py:741](../../tests/core/test_undo/test_collapse_expand.py#L741) | test_a_selection_around_a_boundary_node_is_refused_too | reverted | fixed message match "cannot be collapsed" dropped; exception type kept |
| [tests/core/test_undo/test_collapse_expand.py:749](../../tests/core/test_undo/test_collapse_expand.py#L749) | test_a_refused_collapse_changes_nothing | reverted | fixed message match "cannot be collapsed" dropped; exception type kept |
| [tests/core/test_undo/test_dissolve_reroute.py:207](../../tests/core/test_undo/test_dissolve_reroute.py#L207) | test_dissolve_raises_on_missing_node | reverted | fixed message match "not found" dropped; exception type kept |
| [tests/core/test_undo/test_port_metadata.py:128](../../tests/core/test_undo/test_port_metadata.py#L128) | test_a_declared_port_is_refused | reverted | fixed message match "not resolved" dropped; exception type kept |
| [tests/core/test_undo/test_port_metadata.py:157](../../tests/core/test_undo/test_port_metadata.py#L157) | test_an_unknown_field_is_refused_at_construction | reverted | fixed message match "cannot write" loosened to dynamic/identifier part "widget_key" |
| [tests/core/test_undo/test_set_property_action.py:168](../../tests/core/test_undo/test_set_property_action.py#L168) | test_the_refusal_names_the_mechanism | reverted | fixed message match "holds no own value.*only from its edges" dropped; exception type kept |
| [tests/core/test_undo/test_split_edge_reroute.py:109](../../tests/core/test_undo/test_split_edge_reroute.py#L109) | test_split_action_raises_on_missing_edge | reverted | fixed message match "not found" dropped; exception type kept |
| [tests/core/test_undo/test_split_edge_reroute.py:171](../../tests/core/test_undo/test_split_edge_reroute.py#L171) | test_add_ports_action_raises_on_missing_node | reverted | fixed message match "not found" dropped; exception type kept |
| [tests/core/test_undo/test_split_edge_reroute.py:288](../../tests/core/test_undo/test_split_edge_reroute.py#L288) | test_validate_reroute_outlet_only_is_invalid | reverted | "exactly one inlet and one outlet" to non-empty err |
| [tests/core/test_undo/test_value_steps.py:124](../../tests/core/test_undo/test_value_steps.py#L124) | test_amend_across_merge_keys_is_refused | reverted | fixed message match "another run" loosened to dynamic/identifier part "amend" |
| [tests/core/test_volumes/test_resolve.py:53](../../tests/core/test_volumes/test_resolve.py#L53) | test_unknown_volume_raises | reverted | full message equality to volume key in message |
| [tests/core/test_volumes/test_resolve.py:174](../../tests/core/test_volumes/test_resolve.py#L174) | test_non_string_relative_is_an_escape | reverted | "not a string" to non-empty reason |
| [tests/core/test_volumes/test_resolve.py:185](../../tests/core/test_volumes/test_resolve.py#L185) | test_symlink_loop_is_a_volume_error | reverted | dropped "cannot be resolved"; VolumeError type kept |
| [tests/core/test_volumes/test_store.py:79](../../tests/core/test_volumes/test_store.py#L79) | test_duplicate_add_and_unknown_update_are_refused | reverted | fixed message match "no volume" loosened to dynamic/identifier part "user:volume:nope" |
| [tests/core/test_volumes/test_store.py:128](../../tests/core/test_volumes/test_store.py#L128) | test_reset_is_refused_without_a_suggestion | reverted | fixed message match "no suggested location" loosened to dynamic/identifier part MODELS |
| [tests/core/test_volumes/test_store.py:132](../../tests/core/test_volumes/test_store.py#L132) | test_reset_is_refused_without_a_suggestion | reverted | fixed message match "user volume" loosened to dynamic/identifier part key |
| [tests/core/test_volumes/test_store.py:134](../../tests/core/test_volumes/test_store.py#L134) | test_reset_is_refused_without_a_suggestion | reverted | fixed message match "no volume" loosened to dynamic/identifier part "lib:volume:nope" |
| [tests/core/test_volumes/test_store.py:284](../../tests/core/test_volumes/test_store.py#L284) | test_user_volume_key | reverted | fixed message match "Invalid volume name" loosened to dynamic/identifier part "Bad Name" |
| [tests/core/types/test_primitive_port_default.py:28](../../tests/core/types/test_primitive_port_default.py#L28) | test_float_inlet_with_text_default_raises | reverted | fixed message match "not a valid FLOAT" loosened to dynamic/identifier part "FLOAT" |
| [tests/core/types/test_primitive_type_default.py:13](../../tests/core/types/test_primitive_type_default.py#L13) | test_a_primitive_type_without_a_default_value_is_rejected | reverted | fixed message match "needs a 'value' that is not None" loosened to dynamic/identifier part "value" |
| [tests/core/settings/test_node_size_props.py:23](../../tests/core/settings/test_node_size_props.py#L23) | test_size_adapt_defaults_to_auto | grey | default that decides sizing behaviour (auto vs manual) |
| [tests/core/test_settings/test_field_name_guard.py:38](../../tests/core/test_settings/test_field_name_guard.py#L38) | test_the_error_suggests_a_fix | grey | only asserts a hint in the error text, but the hint is an API spelling (`ui_state=UiState.HIDDEN`) |
| [tests/core/test_authoring/test_plan_node.py:99](../../tests/core/test_authoring/test_plan_node.py#L99) | (plan carries module docstring) | keep | docstring comes from the fixture source module |
| [tests/core/test_debug/test_logging_configurator.py:37](../../tests/core/test_debug/test_logging_configurator.py#L37) | test_root_logger_set_to_log_level_default | keep | checks the configurator applies the setting at construction; INFO literal restates the default (minor) |
| [tests/core/test_debug/test_stall_watchdog.py:37](../../tests/core/test_debug/test_stall_watchdog.py#L37) | (watchdog) | keep | timing file; not copy |
| [tests/core/test_errors/test_boundary.py:43](../../tests/core/test_errors/test_boundary.py#L43) | test_a_plain_exception_is_wrapped_enriched_and_recorded | keep | message computed from operation passed in ("{operation} failed") |
| [tests/core/test_graph/test_load_save_boundary.py:51](../../tests/core/test_graph/test_load_save_boundary.py#L51) | _assert_points_at_haywire_frame | keep | negative check; a copy edit cannot break it (it can go vacuous; fragile) |
| [tests/core/test_graph/test_load_save_boundary.py:60](../../tests/core/test_graph/test_load_save_boundary.py#L60) | test_unreadable_file_is_recorded | keep | operation "Load graph" is an operation key; format_detailed line check is formatting behaviour |
| [tests/core/test_node/test_fold.py:163](../../tests/core/test_node/test_fold.py#L163) | test_a_fold_describes_itself_without_the_author | keep | explicit description= comes from the test fixture node (plumbing) |
| [tests/core/test_node/test_hidden.py:61](../../tests/core/test_node/test_hidden.py#L61) | (uncategorized menu test) | keep | label defined by the test node |
| [tests/core/test_node/test_port_edit_affordance.py:61](../../tests/core/test_node/test_port_edit_affordance.py#L61) | test_it_carries_an_authored_description | keep | description set by the fixture |
| [tests/core/test_settings/test_settings.py:52](../../tests/core/test_settings/test_settings.py#L52) | test_default_values | keep | defaults of a settings class defined in the test |
| [tests/core/test_tomlio.py:52](../../tests/core/test_tomlio.py#L52) | (comments preserved) | keep | fixture comments must survive a rewrite |
| [tests/core/test_undo/test_history_snapshot.py:79](../../tests/core/test_undo/test_history_snapshot.py#L79) | (StepOrigin label) | keep | computed formatting "Farmhand · carol" |

### ui

| Where | Test | Category | Reason |
|---|---|---|---|
| [tests/ui/harness/test_field_list_widget.py:50](../../tests/ui/harness/test_field_list_widget.py#L50) | test_a_bad_key_says_why | delete | only asserts the fixed validation hint "Letters, digits and _ only" is visible; test_a_bad_key_cannot_be_added covers the behaviour |
| [tests/ui/harness/test_structural.py:88](../../tests/ui/harness/test_structural.py#L88) | test_category_headings_present | delete | only asserts four hand-set section heading labels are visible; module docstring updated |
| [tests/ui/test_activity_settings_panel.py:15](../../tests/ui/test_activity_settings_panel.py#L15) | test_panel_label_and_icon_match_the_rest_of_the_feature | delete | restates the real panel's hand-set label "Activity" and icon |
| [tests/ui/graph_canvas/test_pin_menu_panels.py:135](../../tests/ui/graph_canvas/test_pin_menu_panels.py#L135) | test_detach_row_label_follows_the_origin | trim | label spellings -> both non-empty and distinct per origin |
| [tests/ui/harness/test_assisted_upload.py:57](../../tests/ui/harness/test_assisted_upload.py#L57) | test_no_digest_shows_the_notice_and_accepts | trim | literal notice replaced by the product constant NO_DIGEST_NOTICE: still checks the notice shows, not its wording |
| [tests/ui/harness/test_copy_button_browser.py:38](../../tests/ui/harness/test_copy_button_browser.py#L38) | test_copy_button_click_shows_copied_notification | trim | "Copied to clipboard" loosened to: a notification shows and it is not the negative (failure) one |
| [tests/ui/harness/test_field_list_widget.py:72](../../tests/ui/harness/test_field_list_widget.py#L72) | test_a_type_option_shows_the_hover_tip_with_class_library_and_description | trim | dropped "True or False" (BOOL spec description copy); kept "Boolean: BOOL", "Library: haywire-core" (formatted) and the saved_in_files line (state-chosen). Test name still says "description" |
| [tests/ui/panels/test_selection_forms.py:90](../../tests/ui/panels/test_selection_forms.py#L90) | test_an_unstyled_edge_among_styled_ones_greys_with_a_reason | trim | reason literal -> non-empty; status=="greyed" kept |
| [tests/ui/panels/test_selection_forms.py:130](../../tests/ui/panels/test_selection_forms.py#L130) | test_a_reroute_among_the_nodes_greys_with_a_reason | trim | reason literal -> non-empty |
| [tests/ui/skin/test_default_skins_home.py:44](../../tests/ui/skin/test_default_skins_home.py#L44) | test_skin_settings_panel_lives_in_graph_editor | trim | dropped identity.label == "Skin"; registration/surface/order asserts kept |
| [tests/ui/skin/test_stage_render.py:281](../../tests/ui/skin/test_stage_render.py#L281) | test_an_annotation_on_stage_draws_its_text_pins_and_slots_but_no_control_pin | trim | "Double-click to write" replaced by note_text_widget._HINT |
| [tests/ui/test_canvas_handlers/test_stage_visual_layer.py:279](../../tests/ui/test_canvas_handlers/test_stage_visual_layer.py#L279) | _REFUSED (used at :314, :355) | trim | local copy of the refusal text replaced by product constant vl_module.STAGE_EDGE_REFUSED |
| [tests/ui/test_canvas_handlers/test_visual_layer_revert.py:42](../../tests/ui/test_canvas_handlers/test_visual_layer_revert.py#L42) | test_the_revert_notice_names_the_macro | trim | == "Reverted to Blur Stack" -> "Blur Stack" in notice (dynamic part) |
| [tests/ui/test_canvas_handlers/test_visual_layer_revert.py:64](../../tests/ui/test_canvas_handlers/test_visual_layer_revert.py#L64) | test_the_forget_notice_names_the_macro | trim | same, dynamic macro name only |
| [tests/ui/test_folder_tree.py:31](../../tests/ui/test_folder_tree.py#L31) | test_three_levels_eager_then_sentinel | trim | sentinel label "Click to load children" -> one child; sentinel identity still checked via is_sentinel/id |
| [tests/ui/widget/test_note_text_widget.py:117](../../tests/ui/widget/test_note_text_widget.py#L117) | test_empty_text_shows_the_hint | trim | literal replaced by the widget's _HINT constant (private import); italic check kept |
| [tests/ui/widget/test_path_widget.py:323](../../tests/ui/widget/test_path_widget.py#L323) | test_browse_loads_three_levels_and_skips_excluded | trim | sentinel label -> exactly one child; expansion to "d" still checked |
| [tests/ui/extends/codemirror/test_code_intelligence_translation.py:34](../../tests/ui/extends/codemirror/test_code_intelligence_translation.py#L34) | test_render_doc_html_wraps_signature_in_python_codeblock | keep | input passes through |
| [tests/ui/harness/test_assisted_upload.py:26](../../tests/ui/harness/test_assisted_upload.py#L26) | _open helper | keep | "Download in browser" used as readiness locator (fragile) |
| [tests/ui/harness/test_assisted_upload.py:37](../../tests/ui/harness/test_assisted_upload.py#L37) | test_drop_stores_the_file_under_its_name et al. | keep | "stored as <name>", "expected <sha>", "size mismatch: got N" are interpolated |
| [tests/ui/harness/test_flow_meter_browser.py:22](../../tests/ui/harness/test_flow_meter_browser.py#L22) | test_hovering_the_collapsed_bar_shows_the_worst_flows_numbers / test_a_bars_tooltip_is_filled_when_it_opens | keep | name + policy + load/dropped/queue numbers are computed |
| [tests/ui/harness/test_graph_context_menu_pin_detection.py:85](../../tests/ui/harness/test_graph_context_menu_pin_detection.py#L85) | pin/node menu tests | keep | "Edit Source"/"Copy" identify which menu branch opened (locator, fragile) |
| [tests/ui/harness/test_graph_swinglet_connect.py:161](../../tests/ui/harness/test_graph_swinglet_connect.py#L161) | test_a_reverse_drag_is_ignored | keep | "Connection created" is a precondition wait; real assertion is no edgeCreated/notify frame (fragile) |
| [tests/ui/harness/test_inset.py:175](../../tests/ui/harness/test_inset.py#L175) | test_right_click_on_the_body_opens_the_host_card_menu | keep | "Enter" identifies the host card's menu (locator, fragile) |
| [tests/ui/harness/test_inspector_gate.py:97](../../tests/ui/harness/test_inspector_gate.py#L97) | test_read_only_rows_stay_live_in_view | keep | "Class" locator; real assertion is gating |
| [tests/ui/harness/test_keymap_listener.py:36](../../tests/ui/harness/test_keymap_listener.py#L36) | whole file (and other harness echo-probe files) | keep | to_have_text on echo probes of computed state |
| [tests/ui/harness/test_level_mode_gate.py:184](../../tests/ui/harness/test_level_mode_gate.py#L184) | badge/comment/note tests | keep | harness fixture copy as locators |
| [tests/ui/harness/test_models_filters.py:50](../../tests/ui/harness/test_models_filters.py#L50) | test_closing_switches_filters_off_and_reopening_restores_them | keep | placeholder "Search models…" used as locator (fragile) |
| [tests/ui/harness/test_promote_flyout.py:60](../../tests/ui/harness/test_promote_flyout.py#L60) | test_promotion_nests_rather_than_flattening / set_to_none / reset_is_listed | keep | menu structure/presence; labels as locators (fragile) |
| [tests/ui/panel/test_panel_decorator.py:215](../../tests/ui/panel/test_panel_decorator.py#L215) | *_defaults_* identity tests (deprecation "", redraw_on (), hosts (), poll True, etc.) | keep | API-semantic defaults (empty = not deprecated / no subscriptions), not copy |
| [tests/ui/panel/test_ports_panel_visibility.py:82](../../tests/ui/panel/test_ports_panel_visibility.py#L82) | test_the_name_carries_the_pin_style_hover_tip (also test_ui_state_row_state.py:349) | keep | fixture description passed through to tip attrs |
| [tests/ui/panel/test_promoted_row_state.py:130](../../tests/ui/panel/test_promoted_row_state.py#L130) | promoted-row hint tests (:130,:134,:148,:162,:465) | keep | hint chosen by promotion state (computed status); literal wording is fragile |
| [tests/ui/panel/test_promoted_row_state.py:222](../../tests/ui/panel/test_promoted_row_state.py#L222) | menu-item set tests (also test_readonly_row.py:81-121, test_registry_row_reset.py:134-138) | keep | which actions are offered is behaviour; labels serve as identifiers (fragile) |
| [tests/ui/panel/test_render_surface.py:126](../../tests/ui/panel/test_render_surface.py#L126) | render_surface error tests (:126,:180,:313) | keep | substring of interpolated error identifies which guard fired |
| [tests/ui/test_editor_registry.py:71](../../tests/ui/test_editor_registry.py#L71) | label/icon/description/deprecation identity tests (also test_panel_registry.py:108, test_node_theme.py:139, test_panel_decorator.py:37,212, test_theme_registry.py:137, test_signals_vocabulary.py:87) | keep | test fixtures define their own copy; plumbing |
| [tests/ui/test_editor_registry.py:194](../../tests/ui/test_editor_registry.py#L194) | test_opens_rejects_typo | keep | stdlib enum message |
| [tests/ui/test_key_hint.py:98](../../tests/ui/test_key_hint.py#L98) | test_icon_action_appends_the_shortcut_to_its_tooltip | keep | fixture tooltip + computed shortcut |
| [tests/ui/test_label_hierarchy.py:123](../../tests/ui/test_label_hierarchy.py#L123) | test_each_label_tier_carries_its_class | keep | fixture text |
| [tests/ui/test_menu_row.py:130](../../tests/ui/test_menu_row.py#L130) | test_disabled_menu_row_keeps_pointer_events_so_a_tooltip_works | keep | fixture tooltip text, behaviour is pointer events |
| [tests/ui/test_shell_keymap.py:167](../../tests/ui/test_shell_keymap.py#L167) | test_denied_key_command_is_refused_with_a_notice | keep | "<label> needs <tier> access" is formatted from command class + tier |
| [tests/ui/test_signal_handler_decorators.py:73](../../tests/ui/test_signal_handler_decorators.py#L73) | redraw_on/react_on rejection tests (also test_panel_decorator.py:174,190,229) | keep | per-argument diagnostics assembled from inputs / passed-in context |
| [tests/ui/widget/test_path_widget.py:236](../../tests/ui/widget/test_path_widget.py#L236) | test_folder_pick_sets_relative_on_confirm | keep | "Scans:day1" computed; "Select" button locator |

### editor_studio

| Where | Test | Category | Reason |
|---|---|---|---|
| [tests/farmhand/test_activity_settings.py:14](../../tests/farmhand/test_activity_settings.py#L14) | test_history_size_defaults_to_fifty | delete | restates numeric default |
| [tests/graph_editor/test_history_editor.py:146](../../tests/graph_editor/test_history_editor.py#L146) | test_without_an_active_graph_it_says_so | delete | only asserted empty-state copy |
| [tests/graph_editor/test_new_node_flow_render.py:69](../../tests/graph_editor/test_new_node_flow_render.py#L69) | test_the_details_step_without_targets_points_at_haywire_init | delete | only asserted empty-state copy |
| [tests/haystack/test_haystack_settings.py:4](../../tests/haystack/test_haystack_settings.py#L4) | test_default_last_haystack_name_is_empty | delete | restates default "" |
| [tests/haystack/test_haystack_settings.py:11](../../tests/haystack/test_haystack_settings.py#L11) | test_default_new_counter_starts_at_one | delete | restates default 1 |
| [tests/haystack/test_haystack_settings_panel.py:19](../../tests/haystack/test_haystack_settings_panel.py#L19) | test_the_setting_has_a_label_a_user_can_find | delete | label literal only |
| [tests/haystack/test_haystack_settings_panel.py:25](../../tests/haystack/test_haystack_settings_panel.py#L25) | test_the_setting_sits_under_a_flow_meters_heading | delete | category heading literal only |
| [tests/farmhand/test_host_unit.py:386](../../tests/farmhand/test_host_unit.py#L386) | test_connection_hint_explains_missing_agent_when_auth_enabled | trim | prose -> names the command `haywire user add` |
| [tests/graph_editor/test_graph_editor_commands.py:103](../../tests/graph_editor/test_graph_editor_commands.py#L103) | test_graph_editor_paste_uses_position | trim | notify text dropped, kept called-once + type=warning |
| [tests/graph_editor/test_graph_editor_placement_levels.py:124](../../tests/graph_editor/test_graph_editor_placement_levels.py#L124) | test_a_level_deeper_in_a_placement_keeps_the_refusal | trim | notify text dropped (kept called + warning); removed `_REFUSAL` |
| [tests/graph_editor/test_graph_editor_placement_levels.py:139](../../tests/graph_editor/test_graph_editor_placement_levels.py#L139) | test_unlocking_a_placement_root_asks_first | trim | dropped title/confirm_label/message equality; kept `"Filter" in message` |
| [tests/graph_editor/test_graph_editor_placement_levels.py:157](../../tests/graph_editor/test_graph_editor_placement_levels.py#L157) | test_edit_instance_needs_edit | trim | notify text dropped, kept called + warning |
| [tests/graph_editor/test_graph_editor_placement_levels.py:177](../../tests/graph_editor/test_graph_editor_placement_levels.py#L177) | test_lock_button_on_a_placement_root (+186, 621) | trim | prose tooltip -> set_text called once; set_enabled assertions keep the behaviour |
| [tests/graph_editor/test_group_verbs.py:85](../../tests/graph_editor/test_group_verbs.py#L85) | test_a_non_convex_collapse_reports_a_reason_naming_the_node | trim | dropped fixed advice "Add them to the selection"; kept `b.node_id in reason` |
| [tests/graph_editor/test_group_verbs.py:283](../../tests/graph_editor/test_group_verbs.py#L283) | test_edit_instance_row | trim | dropped `class_identity.label == "Edit Instance"`; drawn-row check now compares to the identity label instead of the literal |
| [tests/graph_editor/test_group_verbs.py:355](../../tests/graph_editor/test_group_verbs.py#L355) | test_revert_row_disabled_when_the_macro_is_gone | trim | tooltip equality -> `"Blur copy" in tooltip` (interpolated name); "Revert to Macro" stays as locator |
| [tests/graph_editor/test_history_editor.py:128](../../tests/graph_editor/test_history_editor.py#L128) | test_editor_identity_is_an_edit_tier_context_slot_editor | trim | dropped label == "History" |
| [tests/graph_editor/test_history_editor.py:178](../../tests/graph_editor/test_history_editor.py#L178) | test_an_interiors_history_is_its_files | trim | "History · Rig" -> any label containing "Rig" (display name) |
| [tests/graph_editor/test_inset_skin.py:157](../../tests/graph_editor/test_inset_skin.py#L157) | test_an_empty_stage_shows_the_placeholder | trim | placeholder literal -> exactly one label and not the staged node's label; removed `_PLACEHOLDER` |
| [tests/graph_editor/test_new_node_flow_render.py:80](../../tests/graph_editor/test_new_node_flow_render.py#L80) | test_the_plan_and_result_steps_render | trim | dropped "Will be written" heading; kept registry key, "Single Copy is registered.", Place/Open file (state-dependent buttons) |
| [tests/graph_editor/test_warning_badge.py:56](../../tests/graph_editor/test_warning_badge.py#L56) | test_the_badge_points_to_the_menu_for_a_previous_setup | trim | dropped two source-copy greps; kept `apply_previous_setup not in src`; renamed to test_the_badge_leaves_restoring_a_previous_setup_to_the_menu |
| [tests/haystack/test_graph_entry.py:69](../../tests/haystack/test_graph_entry.py#L69) | test_display_name_falls_back_to_untitled | trim | "Untitled" -> display_name non-empty |
| [tests/haystack/test_haystack_settings_panel.py:44](../../tests/haystack/test_haystack_settings_panel.py#L44) | test_panel_is_registered_under_barns | trim | dropped label == "Haystack"; kept surface and icon |
| [tests/haystack/test_haystack_state.py:59](../../tests/haystack/test_haystack_state.py#L59) | test_create_new_increments_counter_and_adds_entry | trim | f"Untitled {n}" -> filestem endswith counter |
| [tests/haystack/test_open_in_haystack_panel.py:54](../../tests/haystack/test_open_in_haystack_panel.py#L54) | test_panel_decorator_metadata | trim | dropped "Haystack" in label |
| [tests/haystack/test_update_macro.py:354](../../tests/haystack/test_update_macro.py#L354) | test_update_swaps_the_card_and_opens_the_document | trim | undo description "Update Macro" -> can_undo(); kept computed notify text (364) |
| [tests/haystack/test_update_macro.py:383](../../tests/haystack/test_update_macro.py#L383) | test_an_error_opening_the_macro_after_the_swap_is_reported | trim | one warning naming Blur and the error; dropped "Undo restores the instance." |
| [tests/haystack/test_update_macro.py:413](../../tests/haystack/test_update_macro.py#L413) | test_a_failure_opening_the_macro_reaches_the_ledger | trim | same as above with "disk gone" |
| [tests/haystack/test_update_macro.py:437](../../tests/haystack/test_update_macro.py#L437) | test_update_warns_when_the_macro_changed_since_the_detach | trim | one warning naming Blur |
| [tests/haystack/test_update_macro.py:466](../../tests/haystack/test_update_macro.py#L466) | test_update_is_refused_while_the_macro_tab_is_unsaved | trim | "Blur" in message |
| [tests/haystack/test_update_macro.py:565](../../tests/haystack/test_update_macro.py#L565) | test_update_row_acts_on_an_editable_macro | trim | dropped row label literal |
| [tests/haystack/test_update_macro.py:578](../../tests/haystack/test_update_macro.py#L578) | test_update_row_disabled_while_the_macro_tab_is_unsaved | trim | dropped label literal; tooltip -> "Blur" in |
| [tests/haystack/test_update_macro.py:615](../../tests/haystack/test_update_macro.py#L615) | test_update_row_disabled_when_the_macro_is_gone | trim | "Blur" in tooltip |
| [tests/studio/test_docs/test_render.py:253](../../tests/studio/test_docs/test_render.py#L253) | test_readme_inserts_placeholder_marker_when_existing_readme_lacks_it | trim | dropped placeholder prose; marker assertion kept |
| [tests/studio/test_error_hooks.py:80](../../tests/studio/test_error_hooks.py#L80) | test_a_ui_failure_is_recorded_with_session_context_and_toasted | trim | toast text dropped, kept called once + negative |
| [tests/studio/test_haystack_editor_remove.py:182](../../tests/studio/test_haystack_editor_remove.py#L182) | test_remove_stale_binding_id_does_not_crash_or_remove | trim | notify text -> notify called |
| [tests/studio/test_haystack_editor_remove.py:199](../../tests/studio/test_haystack_editor_remove.py#L199) | test_remove_executing_entry_blocked_before_dialog | trim | notify text -> notify called |
| [tests/studio/test_network/test_ip_allowlist_wiring.py:132](../../tests/studio/test_network/test_ip_allowlist_wiring.py#L132) | test_invalid_cidr_in_allowed_ranges_raises_system_exit | trim | dropped "network settings" prose; kept exit code, no middleware, ERROR marker |
| [tests/studio/test_shortcuts_editor.py:157](../../tests/studio/test_shortcuts_editor.py#L157) | test_editor_identity_is_a_context_slot_editor | trim | dropped label == "Shortcuts" |
| [tests/studio/test_shortcuts_editor.py:277](../../tests/studio/test_shortcuts_editor.py#L277) | test_no_shortcuts_shows_the_empty_state | trim | dropped empty-state copy, kept groups == {}; renamed test_no_shortcuts_draws_no_groups |
| [tests/graph_editor/test_locked_node_delete_skip.py:95](../../tests/graph_editor/test_locked_node_delete_skip.py#L95) | test_the_skip_is_reported | reverted | "skipped" -> message non-empty |
| [tests/graph_editor/test_locked_node_delete_skip.py:102](../../tests/graph_editor/test_locked_node_delete_skip.py#L102) | test_an_all_locked_selection_deletes_nothing_and_says_so | reverted | "locked" -> message non-empty |
| [tests/graph_editor/test_new_node_flow.py:211](../../tests/graph_editor/test_new_node_flow.py#L211) | test_an_existing_file_is_refused_live | reverted | "already exists" -> refusal is set |
| [tests/haystack/test_update_macro.py:221](../../tests/haystack/test_update_macro.py#L221) | test_open_macro_with_refuses_an_unsaved_entry | reverted | match "unsaved edits" -> match "Blur" (display name) |
| [tests/haystack/test_update_macro.py:241](../../tests/haystack/test_update_macro.py#L241) | failed-load tests (241, 267, 302, 317) | reverted | fixed match -> match "Blur"; following state assertions carry behaviour |
| [tests/studio/test_docs/test_generate.py:246](../../tests/studio/test_docs/test_generate.py#L246) | test_library_id_for_path_raises_on_ambiguous_shared_parent | reverted | match "Ambiguous library path" -> r"lib_a.*lib_b" (computed matches) |
| [tests/studio/test_network/test_tls_operations.py:102](../../tests/studio/test_network/test_tls_operations.py#L102) | test_setup_twice_is_refused | reverted | dropped match "already exists" (CertError is specific) |
| [tests/farmhand/test_activity_settings.py:20](../../tests/farmhand/test_activity_settings.py#L20) | test_log_path_defaults_to_empty_meaning_off | grey | load-bearing: audit log to disk off by default |
| [tests/farmhand/test_baseline_tools.py:143](../../tests/farmhand/test_baseline_tools.py#L143) | test_list_components_truncated_result_gets_scoping_tip (+153) | grey | agent `help` hint prose "narrow this" |
| [tests/farmhand/test_graph_editor_tools.py:1411](../../tests/farmhand/test_graph_editor_tools.py#L1411) | test_operate_refuses_a_non_operable_port | grey | agent-facing guidance prose + tool name |
| [tests/haystack/test_exception_bail_policy.py:10](../../tests/haystack/test_exception_bail_policy.py#L10) | test_the_policy_defaults_to_branch_and_offers_three_scopes | grey | default "branch" is load-bearing; option set is a contract |
| [tests/haystack/test_graph_entry.py:174](../../tests/haystack/test_graph_entry.py#L174) | test_graph_entry_has_run_settings_by_default | grey | restates autorestart default (see GraphRunSettings grey) |
| [tests/haystack/test_graph_run_settings.py:4](../../tests/haystack/test_graph_run_settings.py#L4) | test_autorestart_defaults_false | grey | load-bearing default (auto-restart graphs) |
| [tests/haystack/test_haystack_settings_panel.py:13](../../tests/haystack/test_haystack_settings_panel.py#L13) | test_flow_meters_are_on_by_default | grey | load-bearing on/off default |
| [tests/studio/test_haystack_editor_remove.py:113](../../tests/studio/test_haystack_editor_remove.py#L113) | test_remove_clean_entry_opens_confirm_with_stays_on_disk_wording (+146, 161) | grey | dialog wording chosen by entry state; only thing distinguishing dirty vs untitled |
| [tests/studio/test_network/test_tls_operations.py:128](../../tests/studio/test_network/test_tls_operations.py#L128) | test_update_without_a_certificate_is_refused | grey | message names the CLI command to run |
| [tests/api/test_deprecated_names.py:61](../../tests/api/test_deprecated_names.py#L61) | test_a_deprecated_name_resolves_and_warns (+84) | keep | message carries computed version/names |
| [tests/execution/test_compile_result.py:17](../../tests/execution/test_compile_result.py#L17) | test_compile_result_failure_carries_message | keep | test-supplied passthrough |
| [tests/farmhand/test_authoring_tools.py:112](../../tests/farmhand/test_authoring_tools.py#L112) | scaffold label tests (+126) | keep | label computed from name / passed input |
| [tests/farmhand/test_baseline_tools.py:212](../../tests/farmhand/test_baseline_tools.py#L212) | help hints naming params (baseline 144/212, marketplace 47/59, authoring 173) | keep | name real parameters/commands an agent uses (contract) |
| [tests/farmhand/test_baseline_tools.py:298](../../tests/farmhand/test_baseline_tools.py#L298) | dismiss summaries (+308) | keep | interpolated seq |
| [tests/farmhand/test_graph_editor_tools.py:325](../../tests/farmhand/test_graph_editor_tools.py#L325) | all `[error_code]` checks | keep | stable MCP error codes agents match on (contract) |
| [tests/farmhand/test_graph_editor_tools.py:484](../../tests/farmhand/test_graph_editor_tools.py#L484) | test_inspect_info_is_the_default_and_carries_no_values | keep | description from haybale-testing SettingsNode fixture (plumbing) |
| [tests/farmhand/test_graph_editor_tools.py:771](../../tests/farmhand/test_graph_editor_tools.py#L771) | test_inspect_names_a_stand_in_by_its_own_key | keep | STAND-IN marker in agent summary is a contract |
| [tests/farmhand/test_graph_editor_tools.py:858](../../tests/farmhand/test_graph_editor_tools.py#L858) | test_inspect_rejects_empty_and_unknown_sections | keep | schema validator message / offending value |
| [tests/farmhand/test_host_unit.py:41](../../tests/farmhand/test_host_unit.py#L41) | format_tool_error tests (+57) | keep | test-supplied message/help; `help:` line format is an agent contract |
| [tests/farmhand/test_host_unit.py:365](../../tests/farmhand/test_host_unit.py#L365) | test_connection_hint_returns_plain_command_when_auth_disabled | keep | runnable command computed from port (contract) |
| [tests/farmhand/test_identity_unit.py:85](../../tests/farmhand/test_identity_unit.py#L85) | test_identity_defaults_auth_required_false | keep | security-relevant written value |
| [tests/graph_editor/test_collapse_toolbar_button.py:145](../../tests/graph_editor/test_collapse_toolbar_button.py#L145) | test_it_carries_exactly_one_tooltip_after_toggling | keep | count "2" is computed; Fold/Unfold chosen by state |
| [tests/graph_editor/test_collapse_toolbar_button.py:154](../../tests/graph_editor/test_collapse_toolbar_button.py#L154) | test_the_tooltip_names_the_action_not_the_state | keep | state-chosen action word is the point of the test |
| [tests/graph_editor/test_compatibility_summary.py:24](../../tests/graph_editor/test_compatibility_summary.py#L24) | test_includes_library_wide_messages | keep | input passthrough |
| [tests/graph_editor/test_graph_container_protocol.py:68](../../tests/graph_editor/test_graph_container_protocol.py#L68) | test_subclass_missing_abstract_member_cannot_instantiate | keep | Python's own message |
| [tests/graph_editor/test_graph_editor_commands.py:312](../../tests/graph_editor/test_graph_editor_commands.py#L312) | test_lock_button_tooltip_names_the_action_a_click_takes | keep | Lock/Unlock chosen by state; shortcut in text |
| [tests/graph_editor/test_graph_editor_placement_levels.py:597](../../tests/graph_editor/test_graph_editor_placement_levels.py#L597) | test_the_confirm_names_the_template_by_its_label | keep | interpolated label |
| [tests/graph_editor/test_graph_notices.py:61](../../tests/graph_editor/test_graph_notices.py#L61) | notices | keep | test-supplied text |
| [tests/graph_editor/test_group_verbs.py:251](../../tests/graph_editor/test_group_verbs.py#L251) | (menu label rows 251-262) | keep | labels are locators for which rows render (behaviour); fragile to label renames |
| [tests/graph_editor/test_history_editor.py:193](../../tests/graph_editor/test_history_editor.py#L193) | (now-marker) | keep | composite computed marker (origin, time) |
| [tests/graph_editor/test_history_editor.py:220](../../tests/graph_editor/test_history_editor.py#L220) | test_pending_steps_are_tagged_and_a_group_opens_to_its_steps | keep | "pending"/"fence" markers reflect computed row kind; "Group of 2 actions" has count; fragile |
| [tests/graph_editor/test_layout_submenu.py:190](../../tests/graph_editor/test_layout_submenu.py#L190) | layout/arrange/rebuild submenu label checks | keep | labels as locators for rows rendered/enabled; fragile |
| [tests/graph_editor/test_lock_toolbar_button.py:184](../../tests/graph_editor/test_lock_toolbar_button.py#L184) | test_it_carries_exactly_one_tooltip_after_toggling (+202, 290) | keep | short state words locked/unlocked chosen by state |
| [tests/graph_editor/test_new_node_flow.py:141](../../tests/graph_editor/test_new_node_flow.py#L141) | (label / source_rows tests) | keep | labels derived from fixture classes |
| [tests/graph_editor/test_new_node_flow_render.py:58](../../tests/graph_editor/test_new_node_flow_render.py#L58) | test_the_source_step_lists_templates / details step | keep | fixture labels, computed file name, interpolated "Starting from Single" |
| [tests/graph_editor/test_operate_tool_fold.py:42](../../tests/graph_editor/test_operate_tool_fold.py#L42) | test_a_port_inside_a_closed_fold_can_be_operated | keep | port name computed |
| [tests/graph_editor/test_promote_flow.py:245](../../tests/graph_editor/test_promote_flow.py#L245) | test_a_swap_refusal_keeps_the_user_on_the_step | keep | test-supplied refusal passthrough |
| [tests/graph_editor/test_save_shown_only_when_dirty.py:128](../../tests/graph_editor/test_save_shown_only_when_dirty.py#L128) | test_the_graph_header_says_not_saved_for_a_document_without_a_file | keep | status word chosen instead of a path (state) |
| [tests/haystack/test_flow_meter.py:98](../../tests/haystack/test_flow_meter.py#L98) | describe() tooltip tests (+105, 177) | keep | formatter output from inputs |
| [tests/haystack/test_notice_row.py:112](../../tests/haystack/test_notice_row.py#L112) | notice row tests (+126, 135) | keep | test-supplied notice text/action label |
| [tests/haystack/test_update_macro.py:422](../../tests/haystack/test_update_macro.py#L422) | test_one_placement_reads_in_the_singular | keep | computed counts/grammar |
| [tests/haystack/test_update_macro.py:600](../../tests/haystack/test_update_macro.py#L600) | test_update_row_disabled_on_a_read_only_install | keep | compares to function output |
| [tests/studio/test_code_intelligence_provider.py:50](../../tests/studio/test_code_intelligence_provider.py#L50) | test_signature_and_doc_returns_plain_text | keep | docstring from test code |
| [tests/studio/test_docs/test_extract.py:113](../../tests/studio/test_docs/test_extract.py#L113) | extract tests (+150) | keep | fixture-defined label/description/docstrings |
| [tests/studio/test_docs/test_render.py:96](../../tests/studio/test_docs/test_render.py#L96) | render tests (+128, 237) | keep | fixture input rendered |
| [tests/studio/test_error_hooks.py:88](../../tests/studio/test_error_hooks.py#L88) | test_a_leaked_refusal_is_toasted_and_not_recorded | keep | refusal text passthrough |
| [tests/studio/test_error_navigation.py:114](../../tests/studio/test_error_navigation.py#L114) | test_open_file_in_studio_publishes_reveal_source | keep | label computed from path |
| [tests/studio/test_error_navigation.py:290](../../tests/studio/test_error_navigation.py#L290) | test_reveal_on_rejects_a_signal_that_is_not_a_reveal | keep | match is a class name |
| [tests/studio/test_errors_editor_navigation.py:117](../../tests/studio/test_errors_editor_navigation.py#L117) | test_open_file_and_component_are_offered_only_for_edit | keep | menu labels as locators for tier-gated items; fragile |
| [tests/studio/test_haystack_editor_reveal_instance.py:52](../../tests/studio/test_haystack_editor_reveal_instance.py#L52) | test_matching_container_publishes_reveal | keep | passthrough |
| [tests/studio/test_log_editor.py:56](../../tests/studio/test_log_editor.py#L56) | test_a_record_logged_after_draw_reaches_the_panel | keep | timing file; test-supplied record |
| [tests/studio/test_network/test_ip_allowlist_wiring.py:168](../../tests/studio/test_network/test_ip_allowlist_wiring.py#L168) | proxy warning tests (+178, 204) | keep | warning names the setting key / header; absence checks depend on it |
| [tests/studio/test_network/test_ip_filter.py:294](../../tests/studio/test_network/test_ip_filter.py#L294) | invalid cidr tests (+299) | keep | stdlib ipaddress message, not our copy |
| [tests/studio/test_network/test_tls_operations.py:166](../../tests/studio/test_network/test_tls_operations.py#L166) | test_update_refuses_to_remove_loopback | keep | names the refused input |
| [tests/studio/test_shortcuts_editor.py:224](../../tests/studio/test_shortcuts_editor.py#L224) | expansion locators "Code"/"Graph" | keep | locators (fixture group names) |
| [tests/studio/test_shortcuts_editor.py:267](../../tests/studio/test_shortcuts_editor.py#L267) | test_a_shadowed_command_is_marked_with_its_winner | keep | winner name interpolated |

### libs_cli

| Where | Test | Category | Reason |
|---|---|---|---|
| [tests/barn/test_questionnaire_editor.py:173](../../tests/barn/test_questionnaire_editor.py#L173) | test_nothing_posted_shows_the_empty_state | delete | only asserts the empty-state copy "No questionnaire" |
| [tests/test_restart_affordance.py:115](../../tests/test_restart_affordance.py#L115) | test_warns_about_unsaved_work | delete | fixed warning copy only |
| [tests/audio/test_exec_audio.py:32](../../tests/audio/test_exec_audio.py#L32) | test_it_is_registered_as_a_type_of_the_audio_library | trim | dropped the label "Audio Execution Signal"; registry key stays |
| [tests/barn/builtin/test_field_list.py:133](../../tests/barn/builtin/test_field_list.py#L133) | test_the_tip_text_lists_description_library_and_whether_it_can_be_saved | trim | exact tip strings are now a structural check: description line, library name, and a saving line that differs by flag |
| [tests/barn/test_fill.py:19](../../tests/barn/test_fill.py#L19) | test_default_is_a_solid_dark_fill | trim | dropped the exact default colour "#1e1e1eff"; kind SOLID stays |
| [tests/barn/test_questionnaire_editor.py:202](../../tests/barn/test_questionnaire_editor.py#L202) | test_submit_enforces_required_and_submit_anyway_does_not | trim | dropped the validation copy "Answer this question."; the status assertions stay |
| [tests/barn/test_questionnaire_editor.py:270](../../tests/barn/test_questionnaire_editor.py#L270) | test_a_submitted_questionnaire_offers_discard_only | trim | dropped the "Submitted" label; the marker checks stay |
| [tests/barn/test_questionnaire_editor.py:280](../../tests/barn/test_questionnaire_editor.py#L280) | test_a_closed_questionnaire_shows_the_empty_state | trim | dropped the empty-state copy; the unanswered count stays |
| [tests/barn/test_volumes_editor.py:97](../../tests/barn/test_volumes_editor.py#L97) | test_header_carries_the_title_and_the_add_button | trim | dropped title "Volumes" and the check that old intro prose is absent; the add-button marker checks stay |
| [tests/barn/test_volumes_editor.py:112](../../tests/barn/test_volumes_editor.py#L112) | test_a_row_is_the_label_over_a_fitted_location_line | trim | dropped the built-in "Project" label and the loop of absent words ("configured", "default", ...); the fixture label "Models" stays |
| [tests/barn/test_volumes_editor.py:160](../../tests/barn/test_volumes_editor.py#L160) | test_the_project_modal_is_read_only_and_shows_the_key | trim | dropped the project volume's hand-set description; key and markers stay |
| [tests/barn/test_volumes_editor.py:232](../../tests/barn/test_volumes_editor.py#L232) | test_a_library_volume_without_a_suggestion_has_no_reset | trim | dropped the hint copy; the no-reset/no-delete markers stay |
| [tests/barn/test_volumes_editor.py:242](../../tests/barn/test_volumes_editor.py#L242) | test_the_add_modal_adds_a_user_volume | trim | "Key: user:volume:scans" loosened to the computed key (SCANS) |
| [tests/image/test_image_settings_panel.py:18](../../tests/image/test_image_settings_panel.py#L18) | test_panel_is_registered_under_barns | trim | dropped the label "Image"; surface stays |
| [tests/image/test_save_image_node.py:146](../../tests/image/test_save_image_node.py#L146) | test_library_default_reaches_node | trim | restated default `quality == 95` is now read from settings; the propagation check stays |
| [tests/libraries/test_surfaces_have_ids.py:120](../../tests/libraries/test_surfaces_have_ids.py#L120) | test_barns_surface_sits_directly_after_app_settings | trim | dropped the label "Barns"; id, icon and order stay |
| [tests/marketstall/test_framework_gate.py:25](../../tests/marketstall/test_framework_gate.py#L25) | test_conflict_names_both_sides | trim | dropped the "Check for updates" hint; both computed versions stay |
| [tests/models/test_cache_sources.py:140](../../tests/models/test_cache_sources.py#L140) | test_cache_sources_names_and_kinds | trim | the label list is now `all(s.label ...)`; the names (ids) stay |
| [tests/models/test_models_editor.py:238](../../tests/models/test_models_editor.py#L238) | test_identity | trim | dropped the label "Models"; requires tier stays |
| [tests/models/test_models_editor.py:288](../../tests/models/test_models_editor.py#L288) | test_remove_confirm_says_when_unused | trim | the literal is now the product constant `editor_module.NOT_USED` |
| [tests/models/test_models_editor.py:395](../../tests/models/test_models_editor.py#L395) | test_a_refused_cancel_says_so | trim | the fixed notify text is now `assert user.notify.messages` (the refusal is still surfaced) |
| [tests/models/test_models_editor.py:471](../../tests/models/test_models_editor.py#L471) | test_remove_never_unlinks_a_symlink_escaping_the_volume | trim | "Nothing to delete" is now `assert user.notify.messages`; the file-safety assertions stay |
| [tests/models/test_models_editor.py:516](../../tests/models/test_models_editor.py#L516) | test_downloads_section_lists_non_catalog_jobs_only | trim | dropped the section title "Downloads"; the computed statuses and markers stay |
| [tests/models/test_models_editor.py:549](../../tests/models/test_models_editor.py#L549) | test_view_lists_graph_with_missing_model_without_walking | trim | dropped the section title "Needed"; the marker, graph name and computed size stay |
| [tests/models/test_models_editor.py:585](../../tests/models/test_models_editor.py#L585) | test_needed_section_absent_when_nothing_is_missing | trim | dropped the absent "Needed" title; the marker check stays |
| [tests/models/test_models_editor.py:692](../../tests/models/test_models_editor.py#L692) | test_hf_section_lists_only_used_files_with_their_users | trim | the full tooltip sentence loosened to the computed "21.0 KB" |
| [tests/models/test_models_editor.py:741](../../tests/models/test_models_editor.py#L741) | test_hf_section_hidden_when_no_cached_file_is_used | trim | dropped the absent "HF cache" text; the markers stay |
| [tests/models/test_models_editor.py:836](../../tests/models/test_models_editor.py#L836) | test_section_headers_count_what_they_list | trim | the computed count headers stay; tooltip prefix "Models volume: " is now a non-empty check; dropped the absent-old-label checks ("Local", "models: ") |
| [tests/models/test_models_editor.py:1008](../../tests/models/test_models_editor.py#L1008) | test_cache_remove_confirmation_names_entries_and_shared_cache | trim | dropped the fixed shared-cache sentence; the computed "Catalog entries: Hubbed" stays |
| [tests/models/test_models_editor.py:1673](../../tests/models/test_models_editor.py#L1673) | test_row_says_non_commercial_unless_flagged | trim | dropped the label text "non-commercial ·"; the count and layout-class checks stay |
| [tests/models/test_models_settings_panel.py:18](../../tests/models/test_models_settings_panel.py#L18) | test_panel_is_registered_under_barns | trim | dropped the label "Models"; surface stays |
| [tests/share_pipeline/test_preconditions.py:632](../../tests/share_pipeline/test_preconditions.py#L632) | (switch-branch remedy test) | trim | dropped the "why" prose "nothing to push to"; the branch name, kind and fix_id stay |
| [tests/share_pipeline/test_preconditions.py:728](../../tests/share_pipeline/test_preconditions.py#L728) | (non-default-branch remedy test) | trim | dropped "keeps its commits"; the computed `git switch <default>` stays |
| [tests/share_pipeline/test_preconditions.py:989](../../tests/share_pipeline/test_preconditions.py#L989) | (add_origin e2e) | trim | the absent-message check "No 'origin' remote is configured" is now `fix_id == "add_origin"` absent |
| [tests/share_pipeline/test_switch_branch_fix.py:148](../../tests/share_pipeline/test_switch_branch_fix.py#L148) | (wrong-branch inform) | trim | "keeps its commits" is now a non-empty remedy check |
| [tests/share_pipeline/test_unreachable_remedy.py:38](../../tests/share_pipeline/test_unreachable_remedy.py#L38) | test_github_ssh_links_the_ssh_key_page | trim | dropped the prose "SSH key"; the URL checks stay |
| [tests/share_pipeline/test_unreachable_remedy.py:47](../../tests/share_pipeline/test_unreachable_remedy.py#L47) | test_github_https_links_the_token_page_not_the_ssh_one | trim | dropped the prose "credential helper"; the URL checks stay |
| [tests/test_deps_cli.py:41](../../tests/test_deps_cli.py#L41) | test_no_drift_exits_ok_and_prints_confirmation | trim | dropped "No dependency drift"; the exit code stays (no script or doc reads this line) |
| [tests/test_deps_cli.py:64](../../tests/test_deps_cli.py#L64) | test_actionable_drift_exits_drift_and_prints_each_kind | trim | dropped the summary "Dependency drift found"; the exit code and computed +/~ lines stay |
| [tests/test_deps_cli.py:81](../../tests/test_deps_cli.py#L81) | test_unresolved_only_is_informational_and_exits_ok | trim | dropped "No dependency drift"; the exit code and the import name stay |
| [tests/test_deps_cli.py:90](../../tests/test_deps_cli.py#L90) | test_no_barn_directory_is_not_a_failure | trim | dropped "Nothing to check"; the exit code stays |
| [tests/test_docs_json_flag.py:106](../../tests/test_docs_json_flag.py#L106) | test_single_form_reports_gaps_then_falls_silent_when_clean | trim | dropped the header copy; the clean confirmation is now "prints something, no gap lines" |
| [tests/test_library_browser_os_gating.py:43](../../tests/test_library_browser_os_gating.py#L43) | test_should_block_install_for_os_returns_message_when_unsupported | trim | dropped the prefix "Not available on this OS"; the computed OS list stays |
| [tests/test_marketplace_config.py:84](../../tests/test_marketplace_config.py#L84) | test_default_offers_the_other_channels_as_comments | trim | dropped the explanatory comment wording ("TOGETHER", "on its own", "newest on PyPI"); the URL comments stay |
| [tests/test_network_cli.py:107](../../tests/test_network_cli.py#L107) | test_expose_refuses_while_the_studio_runs | trim | dropped "a studio is running"; exit code 1 stays |
| [tests/test_restart_affordance.py:54](../../tests/test_restart_affordance.py#L54) | test_renders_restart_button | trim | `.text == "Restart Studio"` loosened to: it is a ui.button and its text is not empty |
| [tests/models/test_resolve_model.py:107](../../tests/models/test_resolve_model.py#L107) | test_resolve_model_missing_raises_named_message | reverted | match loosened to the computed catalog key |
| [tests/models/test_resolver.py:613](../../tests/models/test_resolver.py#L613) | test_file_ref_with_whole_repo_address_is_missing | reverted | dropped the fixed explanation sentence; the exception type and `wanted == []` stay |
| [tests/test_refresh_flow_ui.py:240](../../tests/test_refresh_flow_ui.py#L240) | test_no_project_path_reports_instead_of_advancing | reverted | "No project open" is now `assert flow.error` |
| [tests/test_volumes_cli.py:114](../../tests/test_volumes_cli.py#L114) | test_set_needs_at_least_one_option | reverted | "nothing to change" is now "something is written to stderr"; exit code 1 stays |
| [tests/models/test_model_tools.py:266](../../tests/models/test_model_tools.py#L266) | test_list_help_says_how_to_finish_an_assisted_job | grey | Farmhand tool help and docstring an agent relies on (G2) |
| [tests/scripts/test_claude_hooks.py:102](../../tests/scripts/test_claude_hooks.py#L102) | test_no_write_access_makes_a_contributor ("never merge or release"), test_the_developer_sees_what_the_t3_setup_lacks (267), test_a_worktree_without_its_setup_asks_for_the_import (279-283) | grey | hook context the agent obeys; pure instruction wording (G7) |
| [tests/share_pipeline/test_human_steps.py:52](../../tests/share_pipeline/test_human_steps.py#L52) | test_pending_publisher_checklist_flags_a_non_github_remote; "1. Create the GitHub repository" (58, 99); "do not attempt it yourself" (100) | grey | share checklist wording that agents relay and obey (G5) |
| [tests/test_agent_playbook.py:57](../../tests/test_agent_playbook.py#L57) | test_generated_claude_md_carries_the_playbook | grey | an instruction sentence in the generated agent playbook (G5) |
| [tests/test_agent_playbook.py:79](../../tests/test_agent_playbook.py#L79) | test_the_release_gates_section_creates_and_checks_every_label | grey | "open one only when the owner agrees" is agent instruction; labels and commands are computed (G5) |
| [tests/test_library_manager_dry_run.py:174](../../tests/test_library_manager_dry_run.py#L174) | test_the_default_torch_backend_is_auto | grey | a default that drives behaviour (G3) |
| [tests/test_restart_affordance.py:129](../../tests/test_restart_affordance.py#L129) | test_states_the_relaunch_command | grey | the relaunch command a user must type (see G1) |
| [tests/test_share_cli.py:235](../../tests/test_share_cli.py#L235) | test_findings_say_so_when_there_is_nothing | grey | agent-read share output, fixed copy only (G5) |
| [tests/test_share_cli.py:347](../../tests/test_share_cli.py#L347) | "Ready to release", "already exists on PyPI", "Release PR open, not merged", "Every name already exists on PyPI" | grey | agent-read share output (G5) |
| [tests/test_share_readme_markers.py:274](../../tests/test_share_readme_markers.py#L274) | test_labels_sit_outside_the_fence / test_single_block_when_there_is_no_tag (288) | grey | the generated README label format (G6) |
| [tests/test_ssl_cli.py:83](../../tests/test_ssl_cli.py#L83) | test_setup_explains_the_browser_warning, test_setup_names_the_private_key_as_private (91), test_setup_adopts_an_orphan_* ("left untouched", 115), test_status_loopback_reads_as_a_non_problem (177), test_status_exposed_but_fenced_* (233), test_status_ok_after_setup (241), test_status_not_covered_* ("NOT covered", 250) | grey | the module docstring says the printed wording is the requirement (G4) |
| [tests/update/test_update_check.py:125](../../tests/update/test_update_check.py#L125) | test_startup_mismatch_fires_when_the_pin_is_ahead_of_the_installed | grey | relaunch command; the versions are computed (G1) |
| [tests/update/test_update_confirmed.py:54](../../tests/update/test_update_confirmed.py#L54) | test_the_banner_names_both_versions_and_the_relaunch_command | grey | relaunch command (G1) |
| [tests/audio/test_channel_ports.py:79](../../tests/audio/test_channel_ports.py#L79) | test_merge_without_any_block_is_an_error | keep | trimming the match fails ruff PT011 (match= required on ValueError), so it was reverted |
| [tests/audio/test_dsp.py:50](../../tests/audio/test_dsp.py#L50) | (about 120 short `match="keyword"` across audio/image/models/auth/security/marketstall) | keep | one- to three-word keys tell apart which ValueError was raised, often carrying computed data (channel N, sizes, names); PT011 requires match= anyway |
| [tests/audio/test_exec_audio.py:94](../../tests/audio/test_exec_audio.py#L94) | (adapter chain error) | keep | message built from the two type names |
| [tests/audio/test_source_nodes.py:75](../../tests/audio/test_source_nodes.py#L75) | test_recorder_write_needs_audio | keep | PT011, as above |
| [tests/barn/builtin/test_field_list.py:127](../../tests/barn/builtin/test_field_list.py#L127) | test_a_label_two_libraries_share_names_the_library | keep | labels built from fixture data |
| [tests/barn/builtin/test_field_list.py:144](../../tests/barn/builtin/test_field_list.py#L144) | test_choices_sort_by_label_ignoring_case | keep | sort behaviour on fixture labels |
| [tests/barn/test_questionnaire.py:477](../../tests/barn/test_questionnaire.py#L477) | (error.help) | keep | a farmhand:// docs URI, functional for agents |
| [tests/barn/test_questionnaire_editor.py:183](../../tests/barn/test_questionnaire_editor.py#L183) | test_an_answer_goes_to_the_store | keep | "Editor test" is the fixture title |
| [tests/barn/test_questionnaire_editor.py:212](../../tests/barn/test_questionnaire_editor.py#L212) | test_a_viewer_sees_no_submit_and_cannot_answer | keep | "Submit anyway" works as a locator for an absent button. Fragile: marker `questionnaire-submit-anyway` would be sturdier |
| [tests/barn/test_volumes_editor.py:144](../../tests/barn/test_volumes_editor.py#L144) | test_without_write_access_every_row_only_views | keep | "Scanner drive" is fixture data |
| [tests/barn/test_volumes_editor.py:193](../../tests/barn/test_volumes_editor.py#L193) | test_a_store_error_shows_in_the_edit_modal_and_keeps_it_open | keep | the modal shows the store's message (passed through). Fragile: pins the store's fixed wording |
| [tests/barn/test_volumes_editor.py:217](../../tests/barn/test_volumes_editor.py#L217) | test_a_library_volume_resets_instead_of_deleting | keep | the suggested path is computed |
| [tests/barn/test_volumes_editor.py:277](../../tests/barn/test_volumes_editor.py#L277) | test_invalid_input_in_the_add_modal_shows_the_store_message_and_writes_nothing | keep | store message passed through (fragile, as above) |
| [tests/barn/test_volumes_editor.py:292](../../tests/barn/test_volumes_editor.py#L292) | test_adding_an_existing_name_shows_the_error | keep | store message passed through (fragile) |
| [tests/barn/test_volumes_editor.py:306](../../tests/barn/test_volumes_editor.py#L306) | test_malformed_file_shows_the_message_in_the_modal_instead_of_crashing | keep | store message passed through (fragile) |
| [tests/barn/test_volumes_editor.py:330](../../tests/barn/test_volumes_editor.py#L330) | test_a_session_demoted_after_draw_gets_the_error_in_the_modal | keep | access error passed through (fragile) |
| [tests/marketplace/test_install_flow.py:110](../../tests/marketplace/test_install_flow.py#L110) | test_framework_conflict_blocks_on_selected | keep | the fake source's error is passed through |
| [tests/models/test_describe.py:42](../../tests/models/test_describe.py#L42) | test_the_description_is_plain_text_with_purpose_author_and_licence (+ file) | keep | a formatter (markdown stripping, joining, truncation); "non-commercial" is also a search keyword |
| [tests/models/test_download.py:241](../../tests/models/test_download.py#L241) | (job.error phrases) | keep | locate which failure branch set job.error |
| [tests/models/test_hf.py:352](../../tests/models/test_hf.py#L352) | test_hf_remove_refuses_a_path_outside_the_snapshots | keep | PT011, as above |
| [tests/models/test_model_tools.py:186](../../tests/models/test_model_tools.py#L186) | test_needs_unknown_binding_errors | keep | the help names the next tool to call (functional for agents) |
| [tests/models/test_models_editor.py:275](../../tests/models/test_models_editor.py#L275) | test_remove_confirm_lists_using_graphs_and_deletes | keep | path, size and graph name are computed |
| [tests/models/test_models_editor.py:329](../../tests/models/test_models_editor.py#L329) | (many) "downloading N %", "Sharp · 4x", count headers | keep | progress, names and sizes are computed |
| [tests/models/test_models_editor.py:870](../../tests/models/test_models_editor.py#L870) | test_catalog_row_of_an_unserved_address_says_so_and_has_no_download | keep | status built from the source scheme |
| [tests/models/test_models_editor.py:900](../../tests/models/test_models_editor.py#L900) | test_editor_row_in_a_cache_shows_its_place_and_no_download (+970/979/990/1123) | keep | "Torch Hub cache" is a status computed from the cache source (fragile: it carries the source label) |
| [tests/models/test_models_editor.py:974](../../tests/models/test_models_editor.py#L974) | test_fetched_cache_file_can_be_removed (+994/1177/1205) | keep | "Delete" is a button locator |
| [tests/models/test_models_editor.py:1063](../../tests/models/test_models_editor.py#L1063) | test_cache_remove_confirmation_names_every_entry_sharing_the_file | keep | entry list is computed |
| [tests/models/test_resolve_model.py:113](../../tests/models/test_resolve_model.py#L113) | test_a_file_outside_both_volumes_is_refused | keep | trimming the match fails ruff PT011, so it was reverted |
| [tests/rename/test_report.py:48](../../tests/rename/test_report.py#L48) | test_blocker_remedy_is_printed / test_warning_remedy_is_printed / test_unrecognized_occurrences_are_flagged | keep | fixture messages; the unrecognized line carries a computed count and names |
| [tests/scripts/test_claude_hooks.py:255](../../tests/scripts/test_claude_hooks.py#L255) | (other hook tests) | keep | phrases locate which conditional block the hook emitted; branch names, ids and commands are computed |
| [tests/scripts/test_finish.py:122](../../tests/scripts/test_finish.py#L122) | (refusal phrases) | keep | every refusal exits 1; the short phrase tells them apart (script output agents read) |
| [tests/scripts/test_generate_marketstall.py:106](../../tests/scripts/test_generate_marketstall.py#L106) | test_build_entry_* | keep | description comes from the fixture |
| [tests/scripts/test_tasks.py:273](../../tests/scripts/test_tasks.py#L273) | test_a_missing_root_is_an_error_with_a_help_line | keep | AXI error:/help: format, a contract |
| [tests/share_pipeline/test_haybale_preconditions.py:233](../../tests/share_pipeline/test_haybale_preconditions.py#L233) | (not repo root) | keep | the only locator of which failure fired (fragile) |
| [tests/share_pipeline/test_human_steps.py:44](../../tests/share_pipeline/test_human_steps.py#L44) | test_pending_publisher_checklist_uses_the_remote_and_every_library_name | keep | owner and repo values are computed (PyPI form field layout) |
| [tests/share_pipeline/test_preconditions.py:314](../../tests/share_pipeline/test_preconditions.py#L314) | (host recognition vs reachability, + 359) | keep | the phrases locate which failure fired |
| [tests/share_pipeline/test_unreachable_remedy.py:98](../../tests/share_pipeline/test_unreachable_remedy.py#L98) | test_the_link_label_uses_the_brands_own_capitalization | keep | the label comes from provider data |
| [tests/test_auth_cli.py:48](../../tests/test_auth_cli.py#L48) | test_enable_with_no_admin_exits_1 (+133 network seal) | keep | remedy command tells apart the refusal reason |
| [tests/test_auth_cli.py:60](../../tests/test_auth_cli.py#L60) | test_status_reports_* | keep | computed status words and counts |
| [tests/test_docs_json_flag.py:91](../../tests/test_docs_json_flag.py#L91) | test_all_form_reports_each_library_and_a_total | keep | counts and sorting are computed (a characterization test) |
| [tests/test_farmhand_cli.py:60](../../tests/test_farmhand_cli.py#L60) | test_allow_remote_refuses_without_auth | keep | remedy command |
| [tests/test_init_readme_scaffold.py:62](../../tests/test_init_readme_scaffold.py#L62) | (generated CLAUDE.md / README) | keep | generated agent docs: commands and markers |
| [tests/test_init_scaffolding.py:356](../../tests/test_init_scaffolding.py#L356) | test_only_a_dev_project_is_told_about_the_share_limit | keep | the phrase locates the dev-only note branch (fragile) |
| [tests/test_library_manager_dry_run.py:313](../../tests/test_library_manager_dry_run.py#L313) | test_dry_run_framework_blocked_* / test_dry_run_unproven_failure_does_not_blame_the_framework (339) | keep | "Check for updates" present/absent marks the framework-blamed branch, the regression these tests exist for (fragile) |
| [tests/test_network_cli.py:75](../../tests/test_network_cli.py#L75) | test_expose_refuses_without_auth | keep | names the remedy command, which tells apart why it refused (holds through rewording) |
| [tests/test_restart_affordance.py:85](../../tests/test_restart_affordance.py#L85) | test_click_triggers_graceful_shutdown | keep | "Restart Studio" is a click locator (fragile) |
| [tests/test_restart_affordance.py:101](../../tests/test_restart_affordance.py#L101) | test_custom_reason_is_rendered | keep | the reason is passed in |
| [tests/test_share_cli.py:224](../../tests/test_share_cli.py#L224) | test_findings_* / NEXT:/STOP:/THEN lines (312-779) | keep | the share CLI's NEXT/STOP/THEN protocol is what agents follow; findings lines are computed |
| [tests/test_ssl_cli.py:102](../../tests/test_ssl_cli.py#L102) | test_setup_twice_*, test_update_without_*, test_trust_without_* | keep | remedy command tells apart the failure |
| [tests/test_ssl_cli.py:118](../../tests/test_ssl_cli.py#L118) | test_setup_refuses_while_the_studio_runs | keep | the text comes from the test's own `_refuse` stub (plumbing) |
| [tests/update/test_update_conflict.py:64](../../tests/update/test_update_conflict.py#L64) | (resolver output, "No conflicts found") | keep | resolver text passed through / result branch |

### core — multi-file keep rows

| Where | Test | Category | Reason |
|---|---|---|---|
| tests/core/test_graph/test_interface_growth_docs.py:83,114,142,308,328,394 | (several) | keep | descriptions set by the test itself, checks seeding/propagation |
| tests/core/test_undo/test_port_metadata.py:64-110, test_history_manager.py:218, test_port_declaration.py:177/202, test_graph_identity_metadata.py:140-141 | (several) | keep | round-trip of values the test writes |
| tests/core/test_node/test_decorator.py:23,52,92,228, test_state/test_decorator.py:15,24,47, test_macro/test_macro_registry.py:56,227, test_library/test_haybale_toml.py:245,312, test_volumes/test_resolve.py:198 | (several) | keep | fixture docstrings/labels passed through decorator/registry (plumbing) |
| tests/core/test_volumes/test_store.py:143,232,238; test_libraries/test_library_enabled_callbacks.py:95,267; test_libraries/test_watcher_metadata_refresh.py:209 | (several) | keep | log text used as locator for "a log was written"; developer logs, not UI copy (fragile) |
| ~40 single-word or identifier `match=` (e.g. "locked", "collision", "OPTIONAL", "toppings", node ids, "allowed: none", "IType-only", "no field_class", "config port", "key", "absolute", "project", "NUL", "MAJOR.MINOR.PATCH") | (several) | keep | identifier, computed value or one key term; survives rewording |
| [tests/core/test_session_context_target.py:61](../../tests/core/test_session_context_target.py#L61), signals/test_editor_command.py:40/57, test_access/* defaults, test_catalog_registry.py:364, test_settings_decorator.py:15 | (several) | keep | None/False/EDIT/ADMIN defaults carry behaviour (security, absence) |
| test_node_layout_direction_graph_tier.py:44, test_node_detail_collapse_tiers.py:92/174, test_stage_model.py:51, test_node_props_bag_override.py:61, test_show_widget_strategy.py:32/37, test_swinglet_port.py:50, test_choices_type.py:12, test_stage_skin_fields.py:105 | (several) | keep | defaults that change behaviour or saved-graph meaning (L2R, FULL, patch view, reroute skin, widget strategies) |
