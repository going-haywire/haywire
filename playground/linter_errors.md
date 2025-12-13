(haywire) mfroehli@NX-41545 haywire-repo % uv run ruff check
playground/nodes/utils/NodePanel.py:39:100: E501 Line too long (116 > 99)
   |
38 |             # Node header with drag handle
39 |             with ui.row().classes('w-full items-center justify-between q-pa-xs drag-handle').style('cursor: grab;'):
   |                                                                                                    ^^^^^^^^^^^^^^^^^ E501
40 |                 ui.icon('drag_indicator').classes(
41 |                         'text-grey-6'
   |

scripts/python_repo_distil.py:187:100: E501 Line too long (141 > 99)
    |
185 | …
186 | …
187 | …Python files in `{repo_path}` on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}.*
    |                                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
188 | …
    |

src/haywire/core/errors/haywire_exception.py:1007:100: E501 Line too long (131 > 99)
     |
1006 | …     # Use reversed box drawing (going down instead of up)
1007 | …     lines.append(f"             {indent_spaces}╒═╧═ {base_filename} in {frame['function']} | File \"{frame['file']}\"")
     |                                                                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
1008 | …     lines.append(f"             {indent_spaces}│    │   ┌─────┄┄┄")
1009 | …     lines.append(f"             {indent_spaces}│    └───┤ line {frame['line']}: {frame['code'].strip()}")
     |

src/haywire/core/errors/haywire_exception.py:1009:100: E501 Line too long (117 > 99)
     |
1007 | …     lines.append(f"             {indent_spaces}╒═╧═ {base_filename} in {frame['function']} | File \"{frame['file']}\"")
1008 | …     lines.append(f"             {indent_spaces}│    │   ┌─────┄┄┄")
1009 | …     lines.append(f"             {indent_spaces}│    └───┤ line {frame['line']}: {frame['code'].strip()}")
     |                                                                                          ^^^^^^^^^^^^^^^^^^ E501
1010 | …     lines.append(f"             {indent_spaces}│        └─────┄┄┄")
1011 | …     lines.append(f"             {indent_spaces}│")     
     |

src/haywire/core/errors/haywire_exception.py:1117:100: E501 Line too long (128 > 99)
     |
1115 | …     space_indent = "  " * i
1116 | …     
1117 | …     lines.append(f"           {space_indent}╘═╤═ {base_filename} in {frame['function']} | File \"{frame['file']}\"")
     |                                                                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
1118 | …     lines.append(f"           {space_indent}  │    │   ┌─────┄┄┄")
1119 | …     lines.append(f"           {space_indent}  │    └───┤ line {frame['line']}: {frame['code'].strip()}")
     |

src/haywire/core/errors/haywire_exception.py:1119:100: E501 Line too long (116 > 99)
     |
1117 | …     lines.append(f"           {space_indent}╘═╤═ {base_filename} in {frame['function']} | File \"{frame['file']}\"")
1118 | …     lines.append(f"           {space_indent}  │    │   ┌─────┄┄┄")
1119 | …     lines.append(f"           {space_indent}  │    └───┤ line {frame['line']}: {frame['code'].strip()}")
     |                                                                                          ^^^^^^^^^^^^^^^^^ E501
1120 | …     lines.append(f"           {space_indent}  │        └─────┄┄┄")
1121 | …     lines.append(f"           {space_indent}  │")        
     |

src/haywire/core/graph/editor.py:92:100: E501 Line too long (104 > 99)
   |
90 |         # Notify callbacks (with error handling to prevent one bad callback 
91 |         # from breaking others)
92 |         for callback in self._change_callbacks[:]:  # Copy list to prevent modification during iteration
   |                                                                                                    ^^^^^ E501
93 |             try:
94 |                 callback()
   |

src/haywire/core/library/base.py:34:100: E501 Line too long (144 > 99)
   |
32 | …
33 | …
34 | …uple[str, Optional[List[str]]]] = {} # registry_cls -> (folder_path, exclude_patterns)
   |                                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
35 | …
36 | …y default
   |

src/haywire/core/library/base.py:134:100: E501 Line too long (150 > 99)
    |
132 | …atcher:
133 | …ntity, registry, self.debounce_delay)
134 | …tarted watching '{folder_path[len(self.identity.folder_path):]}' for hot reload events.")
    |                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
135 | …
136 | …
    |

src/haywire/core/library/base.py:151:100: E501 Line too long (150 > 99)
    |
149 | …atcher:
150 | …
151 | …topped watching '{folder_path[len(self.identity.folder_path):]}' for hot reload events.")
    |                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
    |

src/haywire/core/library/identity.py:14:100: E501 Line too long (137 > 99)
   |
12 | …
13 | …y, defaults to label if not set
14 | …d haywire libraries. For hot reloading to work, the dependencies must be specified.
   |                                               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
15 | … file changes
16 | …der, auto set during registration
   |

src/haywire/core/library/registry.py:230:100: E501 Line too long (112 > 99)
    |
228 |             for item in os.listdir(directory):
229 |                 item_path = os.path.join(directory, item)
230 |                 if os.path.isdir(item_path) and not item.startswith('.') and not item.startswith('__pycache__'):
    |                                                                                                    ^^^^^^^^^^^^^ E501
231 |                     module_paths = self._check_library_structure(item, item_path)
232 |                     for module_path in module_paths:
    |

src/haywire/core/library/registry.py:236:100: E501 Line too long (100 > 99)
    |
234 |                         module_folder_name = os.path.basename(module_path)
235 |                         lib_folders[module_folder_name] = module_path
236 |                         logger.info(f"Valid library found: '{module_folder_name}' at {module_path}")
    |                                                                                                    ^ E501
237 |
238 |         except OSError as e:
    |

src/haywire/core/library/registry.py:273:100: E501 Line too long (120 > 99)
    |
271 |                     for item in os.listdir(library_path):
272 |                         item_path = os.path.join(library_path, item)
273 |                         if os.path.isdir(item_path) and not item.startswith('.') and not item.startswith('__pycache__'):
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^ E501
274 |                             init_path = os.path.join(item_path, '__init__.py')
275 |                             if os.path.exists(init_path):
    |

src/haywire/core/library/registry.py:285:100: E501 Line too long (110 > 99)
    |
283 |                     f"Library '{library_id}': "
284 |                     f"Invalid library structure at '{library_path}'. "
285 |                     f"Expected either '__init__.py' (flat) or 'pyproject.toml' with nested modules (package)."
    |                                                                                                    ^^^^^^^^^^^ E501
286 |                 )
    |

src/haywire/core/library/registry.py:293:100: E501 Line too long (100 > 99)
    |
291 |         return module_paths    
292 |
293 |     def _load_library_class(self, library_folder_name: str, library_path: str) -> type[BaseLibrary]:
    |                                                                                                    ^ E501
294 |         """Load a library class from its path"""       
295 |         try:
    |

src/haywire/core/library/registry.py:305:100: E501 Line too long (116 > 99)
    |
303 |                         f"Library '{library_folder_name}': "
304 |                         f"Has no a valid 'class_identity'. "
305 |                         f"Check if @library decorator is applied to the class in '__init__.py' at '{library_path}'")
    |                                                                                                    ^^^^^^^^^^^^^^^^^ E501
306 |             else:
307 |                 logger.error(
    |

src/haywire/core/library/registry.py:317:100: E501 Line too long (100 > 99)
    |
315 |             raise LibraryLoadError(f"Failed instantiating library {library_folder_name}: {e}")
316 |
317 |     def _load_module_and_metadata(self, library_id: str, library_path: str) -> Optional[ModuleType]:
    |                                                                                                    ^ E501
318 |         """
319 |         Load module from a library's __init__.py.
    |

src/haywire/core/library/registry.py:395:100: E501 Line too long (100 > 99)
    |
393 |         for search_path in self._library_root_paths:
394 |             # Skip core libraries path if it's in the list
395 |             if self.core_libraries_path and os.path.samefile(search_path, self.core_libraries_path):
    |                                                                                                    ^ E501
396 |                 continue
    |

src/haywire/core/library/registry.py:417:100: E501 Line too long (105 > 99)
    |
415 |         return discovered
416 |     
417 |     def _instantiate_libraries(self, discovered: Dict[str, DiscoveredLibrary]) -> Dict[str, BaseLibrary]:
    |                                                                                                    ^^^^^^ E501
418 |         """Instantiate all discovered libraries"""
419 |         instantiated = {}
    |

src/haywire/core/library/utils.py:108:100: E501 Line too long (102 > 99)
    |
107 |     if filtered_frames:
108 |         return ''.join(traceback.format_list(filtered_frames)) + f"\n{exc_type.__name__}: {exc_value}"
    |                                                                                                    ^^^ E501
109 |     else:
110 |         return f"{exc_type.__name__}: {exc_value}"
    |

src/haywire/core/node/factory.py:14:100: E501 Line too long (101 > 99)
   |
12 | from .base import BaseNode, node
13 | from .registry import NodeRegistry
14 | from ..registry.lifecycle_event import LifeCycleEvent, LiveCycleBatchCallback, LiveCycleEventCallback
   |                                                                                                    ^^ E501
   |

src/haywire/core/node/factory.py:67:100: E501 Line too long (123 > 99)
   |
66 |         # individual event notification callbacks
67 |         self._livecycle_event_subscribers: Dict[str, List[LiveCycleEventCallback]] = {} # registry_key -> list of callbacks
   |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^ E501
68 |         
69 |         # Register this factory for livecycle events from node registry hot reloads
   |

src/haywire/core/node/factory.py:101:100: E501 Line too long (101 > 99)
    |
100 |         This is called by the NodeRegistry when a node class is reloaded, added, or removed.
101 |         It forwards the notification to all registered hot reload listeners (typically NodeWrappers).
    |                                                                                                    ^^ E501
102 |         
103 |         Args:
    |

src/haywire/core/node/node_wrapper.py:15:100: E501 Line too long (121 > 99)
   |
14 | from ..errors import HaywireException
15 | from ..registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType, LiveCycleBatchCallback, LiveCycleEventCallback
   |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^ E501
16 |
17 | if TYPE_CHECKING:
   |

src/haywire/core/node/node_wrapper.py:141:100: E501 Line too long (106 > 99)
    |
139 |         with self._lock:
140 |             # Remove event subscription
141 |             self._node_factory.remove_event_subscriber(self.registry_key, self._listen_on_livecycle_event)
    |                                                                                                    ^^^^^^^ E501
142 |                         
143 |             self._livecycle_subscribers.clear()
    |

src/haywire/core/node/node_wrapper.py:163:100: E501 Line too long (114 > 99)
    |
161 |             if not lc_event.matches_registry_key(self.registry_key):
162 |                 logging.warning(
163 |                     f"NodeWrapper {self.node_id}: Received unrelated live cycle event for {lc_event.registry_key}"
    |                                                                                                    ^^^^^^^^^^^^^^^ E501
164 |                 )
165 |                 return
    |

src/haywire/core/node/node_wrapper.py:169:100: E501 Line too long (106 > 99)
    |
167 |             with self._lock:
168 |                 logging.info(
169 |                     f"NodeWrapper {self.node_id}: Detected live cycle event - {lc_event.event_type.value}"
    |                                                                                                    ^^^^^^^ E501
170 |                 )
    |

src/haywire/core/node/node_wrapper.py:178:100: E501 Line too long (105 > 99)
    |
176 |                     if _instance is not None:
177 |                         # get current position
178 |                         position = (self._node_instance.ui_state.posX, self._node_instance.ui_state.posY)
    |                                                                                                    ^^^^^^ E501
179 |                         self._node_instance = _instance
180 |                         # restore position
    |

src/haywire/core/node/node_wrapper.py:199:100: E501 Line too long (104 > 99)
    |
197 |                     self.state.is_valid = False
198 |                     if lc_event.is_removal():
199 |                         # The registry doesn't flag this as an error, but we cannot use the node anymore
    |                                                                                                    ^^^^^ E501
200 |                         # thereforee generate our own error state and enhance the event
201 |                         error = HaywireException(
    |

src/haywire/core/node/node_wrapper.py:203:100: E501 Line too long (128 > 99)
    |
201 |                         error = HaywireException(
202 |                             operation="Node Removed",
203 |                             message=f"Node '{self.registry_key}' has been removed from the registry and can no longer be used.",
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
204 |                         ).enrich(
205 |                             node_id=self.node_id,
    |

src/haywire/core/node/node_wrapper.py:236:100: E501 Line too long (126 > 99)
    |
234 |         return self._generate_node_instance(lc_event)
235 |
236 |     def _generate_node_instance(self, lc_event: LifeCycleEvent, _is_error: bool = False) -> tuple['BaseNode', LifeCycleEvent]:
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
237 |         """
238 |         Generate a node instance based on the lifecycle event.
    |

src/haywire/core/node/node_wrapper.py:360:100: E501 Line too long (102 > 99)
    |
358 |             event: The live cycle event to propagate to observers
359 |         """
360 |         for callback in self._livecycle_subscribers[:]:  # Copy to avoid modification during iteration
    |                                                                                                    ^^^ E501
361 |             callback(event)
    |

src/haywire/core/node/node_wrapper.py:401:100: E501 Line too long (111 > 99)
    |
400 |     def __repr__(self) -> str:
401 |         return f"NodeWrapper(id={self.node_id}, registry_key={self.registry_key}, valid={self.state.is_valid})"
    |                                                                                                    ^^^^^^^^^^^^ E501
    |

src/haywire/core/node/registry.py:29:100: E501 Line too long (105 > 99)
   |
27 |             return False
28 |
29 |     def _register_class(self, node_cls: type[BaseNode], library_identity: LibraryIdentity) -> str | None:
   |                                                                                                    ^^^^^^ E501
30 |         """
31 |         Register a node class with library metadata.
   |

src/haywire/core/node/registry.py:50:100: E501 Line too long (109 > 99)
   |
48 |         if node_cls.class_identity._is_error:
49 |             if self._error_node is not None:
50 |                 if node_cls.class_identity._error_priority > self._error_node.class_identity._error_priority:
   |                                                                                                    ^^^^^^^^^^ E501
51 |                     logging.warning(
52 |                         f"Overriding already registered error node: '{self._error_node.class_identity.registry_key}'."
   |

src/haywire/core/node/registry.py:52:100: E501 Line too long (118 > 99)
   |
50 | …     if node_cls.class_identity._error_priority > self._error_node.class_identity._error_priority:
51 | …         logging.warning(
52 | …             f"Overriding already registered error node: '{self._error_node.class_identity.registry_key}'."
   |                                                                                          ^^^^^^^^^^^^^^^^^^^ E501
53 | …             f" with : '{node_cls.class_identity.registry_key}'"
54 | …             f" due to higher _error_priority ({node_cls.class_identity._error_priority} > {self._error_node.class_identity._error_pr…
   |

src/haywire/core/node/registry.py:54:100: E501 Line too long (153 > 99)
   |
52 | …node: '{self._error_node.class_identity.registry_key}'."
53 | …gistry_key}'"
54 | …e_cls.class_identity._error_priority} > {self._error_node.class_identity._error_priority})"
   |                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
55 | …
56 | …
   |

src/haywire/core/node/registry.py:73:100: E501 Line too long (104 > 99)
   |
71 |         if self.get(registry_key) == self._error_node:
72 |             self._error_node = None
73 |             logging.warning(f"Error node '{registry_key}' unregistered, no error node left in registry")
   |                                                                                                    ^^^^^ E501
74 |     
75 |         return super()._unregister(registry_key)
   |

src/haywire/core/registry/base.py:63:100: E501 Line too long (101 > 99)
   |
61 |         # it keeps track of what was the last event type for each class, 
62 |         # even those that have been removed
63 |         self._regkey_to_last_lifecycle_event: Dict[str, LifeCycleEvent] = {}  # registry_key -> event
   |                                                                                                    ^^ E501
64 |
65 |         # BaseClassRegistry specific attributes
   |

src/haywire/core/registry/base.py:67:100: E501 Line too long (100 > 99)
   |
65 |         # BaseClassRegistry specific attributes
66 |         self._regkey_to_class_name: Dict[str, str] = {}  # registry_key -> class name
67 |         self._module_to_registry_keys: Dict[str, list[str]] = {}  #  module -> list of registry_keys
   |                                                                                                    ^ E501
68 |         self._folder_to_library: Dict[str, LibraryIdentity] = {} # folder_path -> library_identity
   |

src/haywire/core/registry/base.py:71:100: E501 Line too long (105 > 99)
   |
70 |         # Hot reload callback management
71 |         self._lifecycle_event_queue: List[LifeCycleEvent] = []  # Queue of events to process after reload
   |                                                                                                    ^^^^^^ E501
72 |
73 |         self._registry_subscribers: List[HotReloadRegistry] = []  # Other registries that depend on this one
   |

src/haywire/core/registry/base.py:73:100: E501 Line too long (108 > 99)
   |
71 |         self._lifecycle_event_queue: List[LifeCycleEvent] = []  # Queue of events to process after reload
72 |
73 |         self._registry_subscribers: List[HotReloadRegistry] = []  # Other registries that depend on this one
   |                                                                                                    ^^^^^^^^^ E501
74 |         self._batch_event_subscribers: List[LiveCycleBatchCallback] = []  # Direct consumers (factories, etc.)
   |

src/haywire/core/registry/base.py:74:100: E501 Line too long (110 > 99)
   |
73 |         self._registry_subscribers: List[HotReloadRegistry] = []  # Other registries that depend on this one
74 |         self._batch_event_subscribers: List[LiveCycleBatchCallback] = []  # Direct consumers (factories, etc.)
   |                                                                                                    ^^^^^^^^^^^ E501
75 |
76 |     @abstractmethod
   |

src/haywire/core/registry/base.py:107:100: E501 Line too long (119 > 99)
    |
105 |         return list(self._classes.keys())
106 |
107 |     def _register(self, registry_key: str, cls: Any, library_identity: Optional[LibraryIdentity] = None) -> str | None:
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^ E501
108 |         """
109 |         Register a class with its name and optional metadata
    |

src/haywire/core/registry/base.py:113:100: E501 Line too long (106 > 99)
    |
111 |             registry_key (str): The haywire registry_key of the class to register
112 |             cls (Any): The class to register
113 |             library_identity (Optional[LibraryIdentity]): The library identity to associate with the class
    |                                                                                                    ^^^^^^^ E501
114 |         Returns:
115 |             str: The haywire registry_key of the registered class
    |

src/haywire/core/registry/base.py:119:100: E501 Line too long (242 > 99)
    |
117 | …
118 | …
119 | … class_identity attribute. Cannot register. This is likely due to a missing condition in the implementation of the registry's class filter method.")
    |       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
120 | …
121 | …
    |

src/haywire/core/registry/base.py:127:100: E501 Line too long (107 > 99)
    |
125 |                 f"Attempt to register Node '{cls.class_identity.label}' "
126 |                 f"under an existing registry_key '{registry_key}'. "
127 |                 f"This is not allowed. Indication of double use of a node registry_id or node class name.")
    |                                                                                                    ^^^^^^^^ E501
128 |
129 |         # Register the class
    |

src/haywire/core/registry/base.py:173:100: E501 Line too long (124 > 99)
    |
171 |     # ============================================================================
172 |
173 |     def add_folder(self, folder_path: str, library_identity: LibraryIdentity, exclude_patterns: Optional[list[str]] = None):
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^ E501
174 |         """
175 |         Initial scan of the folder for classes matching the registry's class filter
    |

src/haywire/core/registry/base.py:195:100: E501 Line too long (100 > 99)
    |
193 |         logging.info(
194 |             f"Library '{library_identity.label}': START Scanning folder "
195 |             f"'{folder_path[len(library_identity.folder_path):]}' for files to register classes...")
    |                                                                                                    ^ E501
196 |
197 |         file_paths = self.folder_scan_for_pyfiles(folder_path, exclude_patterns)
    |

src/haywire/core/registry/base.py:216:100: E501 Line too long (116 > 99)
    |
214 |                         exception=e,
215 |                         operation="Registry folder import",
216 |                         message=f"Failed while importing folder '{file_path}' in library '{library_identity.label}'"
    |                                                                                                    ^^^^^^^^^^^^^^^^^ E501
217 |                     ).enrich(
218 |                         module_name=module_name,
    |

src/haywire/core/registry/base.py:233:100: E501 Line too long (127 > 99)
    |
231 |             f"{len(file_paths)} files processed.")
232 |
233 |     def remove_folder(self, folder_path: str, library_identity: LibraryIdentity, exclude_patterns: Optional[list[str]] = None):
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
234 |         """ 
235 |         Remove all classes associated with a library_identity from this registry.
    |

src/haywire/core/registry/base.py:263:100: E501 Line too long (118 > 99)
    |
261 |                         exception=e,
262 |                         operation="Registry folder import",
263 |                         message=f"Failed while importing folder '...{rel_path}' in library '{library_identity.label}'"
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^ E501
264 |                     ).enrich(
265 |                         module_name=module_name,
    |

src/haywire/core/registry/base.py:322:100: E501 Line too long (148 > 99)
    |
320 | …
321 | …s modified but not yet loaded
322 | …dentity.label}': Module '{module_name}' not found in sys.modules. Creating new module.")
    |                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
323 | …rary_identity)
324 | …
    |

src/haywire/core/registry/base.py:346:100: E501 Line too long (122 > 99)
    |
344 |                             exception=e,
345 |                             operation="Registry Hotreload File Module Reload",
346 |                             message=f"Failed reloading module '{module_name}' in library '{event.library_identity.label}'"
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^ E501
347 |                         ).enrich(
348 |                             registry_key=key,
    |

src/haywire/core/registry/base.py:366:100: E501 Line too long (127 > 99)
    |
364 |                     exception=e,
365 |                     operation="Registry Hotreload Callback",
366 |                     message=f"Failed notifying about file {event.event_type.value} in library '{event.library_identity.label}'"
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
367 |                 ).enrich(
368 |                     module_name=locals().get('module_name', 'unknown'),
    |

src/haywire/core/registry/base.py:392:100: E501 Line too long (112 > 99)
    |
390 |             return  # Skip processing if validation failed
391 |
392 |         added_classes, _ = self.module_scan_for_classes(module_name, library_identity, self._class_filter, True)
    |                                                                                                    ^^^^^^^^^^^^^ E501
393 |         if added_classes:
394 |             # Get tracking scopes from library dependencies
    |

src/haywire/core/registry/base.py:414:100: E501 Line too long (119 > 99)
    |
414 |     def _on_change(self, module_name: str, library_identity: LibraryIdentity, event: Optional[FileChangeEvent] = None):
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^ E501
415 |         """
416 |         re-registering existing classes within the module
    |

src/haywire/core/registry/base.py:421:100: E501 Line too long (101 > 99)
    |
419 |         Args:
420 |             module_name (str): The module name that has changed.
421 |             event (Optional[FileChangeEvent]): The file change event (used to track reloaded modules)
    |                                                                                                    ^^ E501
422 |         Returns:
423 |             [list,list]: [(List of classes to be registered), (List of haywire class names to be unregistered)]
    |

src/haywire/core/registry/base.py:423:100: E501 Line too long (111 > 99)
    |
421 |             event (Optional[FileChangeEvent]): The file change event (used to track reloaded modules)
422 |         Returns:
423 |             [list,list]: [(List of classes to be registered), (List of haywire class names to be unregistered)]
    |                                                                                                    ^^^^^^^^^^^^ E501
424 |         """
425 |         if module_name is None:
    |

src/haywire/core/registry/base.py:480:100: E501 Line too long (165 > 99)
    |
478 | …
479 | …
480 | …ule_name, library_identity=library_identity, class_filter=self._class_filter, force_reload=True)
    |                                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
481 | …
482 | …
    |

src/haywire/core/registry/base.py:491:100: E501 Line too long (112 > 99)
    |
490 |                 # Store old class info for re-registration
491 |                 mod_to_class_name_mapping: Dict[str, str] = {} # module class name -> haywire class registry_key
    |                                                                                                    ^^^^^^^^^^^^^ E501
492 |                 for mod_class_reg_key in class_reg_keys_to_update:
493 |                     mod_to_class_name_mapping[self._regkey_to_class_name[mod_class_reg_key]] = mod_class_reg_key
    |

src/haywire/core/registry/base.py:493:100: E501 Line too long (112 > 99)
    |
491 | …     mod_to_class_name_mapping: Dict[str, str] = {} # module class name -> haywire class registry_key
492 | …     for mod_class_reg_key in class_reg_keys_to_update:
493 | …         mod_to_class_name_mapping[self._regkey_to_class_name[mod_class_reg_key]] = mod_class_reg_key
    |                                                                                          ^^^^^^^^^^^^^ E501
494 | …         # check if the registered old class name matches a class name in the new module
495 | …         class_to_remove = next((cls for cls in classes_to_add if cls.__name__ == self._regkey_to_class_name[mod_class_reg_key]), No…
    |

src/haywire/core/registry/base.py:495:100: E501 Line too long (146 > 99)
    |
493 | …to_class_name[mod_class_reg_key]] = mod_class_reg_key
494 | …e matches a class name in the new module
495 | …classes_to_add if cls.__name__ == self._regkey_to_class_name[mod_class_reg_key]), None)
    |                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
496 | …
497 | … avoid re-registering it
    |

src/haywire/core/registry/base.py:503:100: E501 Line too long (103 > 99)
    |
501 |                 for mod_class_reg_key in mod_to_class_name_mapping:
502 |                     if hasattr(module, mod_class_reg_key):
503 |                         # to update a class, we need to unregister the old one and register the new one
    |                                                                                                    ^^^^ E501
504 |                         new_class: Type[Any] = getattr(module, mod_class_reg_key)
505 |                         old_class_name = mod_to_class_name_mapping[mod_class_reg_key]
    |

src/haywire/core/registry/base.py:523:100: E501 Line too long (115 > 99)
    |
521 |                     logging.info(
522 |                         f"Library '{library_identity.label}': "
523 |                         f"...Re-loaded and re-registered {new_cls.class_identity.registry_key} from {module_name}")
    |                                                                                                    ^^^^^^^^^^^^^^^^ E501
524 |                     # Notify customer callbacks about reloaded class
525 |                     if new_key:
    |

src/haywire/core/registry/base.py:623:100: E501 Line too long (112 > 99)
    |
621 |         return snapshot
622 |  
623 |     def _rollback_snapshot(self, module_name: str, snapshot: Dict[str, Any], library_identity: LibraryIdentity):
    |                                                                                                    ^^^^^^^^^^^^^ E501
624 |         """Restore module from snapshot after failed reload"""            
625 |         if snapshot:
    |

src/haywire/core/registry/base.py:778:100: E501 Line too long (118 > 99)
    |
776 |             except Exception as e:
777 |                 logging.error(
778 |                     f"Registry subscriber '{registry.__class__.__name__}' callback failed for {event.file_path}: {e}",
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^ E501
779 |                     exc_info=True
780 |                 )
    |

src/haywire/core/registry/dependency_graph.py:309:100: E501 Line too long (109 > 99)
    |
307 |         )
308 |     
309 |     def get_reload_plan(self, changed_module: str, exclude_modules: Optional[Set[str]] = None) -> ReloadPlan:
    |                                                                                                    ^^^^^^^^^^ E501
310 |         """
311 |         Generate a reload plan for when a module changes.
    |

src/haywire/core/registry/dependency_graph.py:502:100: E501 Line too long (100 > 99)
    |
500 |         return dep_count
501 |     
502 |     def _extract_direct_dependencies(self, module_name: str, scope_prefixes: List[str]) -> Set[str]:
    |                                                                                                    ^ E501
503 |         """
504 |         Extract direct (first-order) module dependencies by parsing source code.
    |

src/haywire/core/registry/folder_scan.py:67:100: E501 Line too long (125 > 99)
   |
65 |         module_prefix = self.resolve_module_name(library_dir)
66 |         if not module_prefix:
67 |             logging.warning(f"Could not resolve module name for {library_path}. No __init__.py found in parent directories.")
   |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
68 |             return []
   |

src/haywire/core/registry/folder_scan.py:127:100: E501 Line too long (140 > 99)
    |
125 | …
126 | …
127 | …y_root: Optional[str] = None, module_prefix: Optional[str] = None) -> Optional[str]:
    |                                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
128 | …
129 | …ibrary root.
    |

src/haywire/core/registry/folder_scan.py:137:100: E501 Line too long (119 > 99)
    |
136 |         Returns:
137 |             Fully qualified module name (e.g., 'haywire.libraries.core.nodes.math_nodes' or 'example.nodes.math_nodes')
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^ E501
138 |         """
139 |         file_path = Path(file_path).resolve()
    |

src/haywire/core/types/base.py:40:100: E501 Line too long (102 > 99)
   |
38 |         return adapter_registry.has_adapter(type(self), type_cls)
39 |
40 |     def get_adapter(self, type_cls: type[BaseType], adapter_registry: AdapterRegistry) -> BaseAdapter:
   |                                                                                                    ^^^ E501
41 |         return adapter_registry.get_adapter(type(self), type_cls)
   |

src/haywire/core/types/base.py:79:100: E501 Line too long (100 > 99)
   |
77 |         except Exception as e:
78 |             raise TypeError(
79 |                 f"Cannot create default instance of {cls.__name__} using default={default_kwargs}. "
   |                                                                                                    ^ E501
80 |                 f"Consider overriding create_default() classmethod for complex initialization. "
81 |                 f"Original error: {e}"
   |

src/haywire/core/types/decorator.py:125:100: E501 Line too long (100 > 99)
    |
123 |             kwargs.setdefault('registry_id', inner_cls.__name__)
124 |             kwargs.setdefault('label', inner_cls.__name__)
125 |             kwargs.setdefault('description', inner_cls.__doc__.strip() if inner_cls.__doc__ else '')
    |                                                                                                    ^ E501
126 |             identity_dict = kwargs
    |

src/haywire/core/types/pipe.py:34:100: E501 Line too long (114 > 99)
   |
32 |         # Update connection status based on remaining sources
33 |         # Use polymorphic has_sources method
34 |         self.target_inlet.is_connected = self.target_inlet.data.has_sources() if self.target_inlet.data else False
   |                                                                                                    ^^^^^^^^^^^^^^^ E501
   |

src/haywire/core/types/utils.py:164:100: E501 Line too long (112 > 99)
    |
163 |     # Store creation recipe for serialization
164 |     if type_cls.class_identity.registry_key and not type_cls.class_identity.registry_key.startswith('default:'):
    |                                                                                                    ^^^^^^^^^^^^^ E501
165 |         method_name = 'as_inlet' if port_class.__name__ == 'PortInlet' else 'as_outlet'
166 |         port._creation_recipe = {
    |

src/haywire/core/undo/actions/graph_actions.py:36:100: E501 Line too long (102 > 99)
   |
34 |             description: Optional description override
35 |         """
36 |         # Use library label if available, otherwise fallback to identity name or node_id or class name
   |                                                                                                    ^^^ E501
37 |         super().__init__(description or f"Add node '{registry_key}'")
38 |         self.graph = graph
   |

src/haywire/core/undo/actions/graph_actions.py:46:100: E501 Line too long (122 > 99)
   |
44 |     def _execute_impl(self) -> None:
45 |         """Add the node to the graph."""
46 |         self.wrapper = NodeWrapper(registry_key=self.registry_key, node_factory=self.node_factory, position=self.position)
   |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^ E501
47 |         if not self.wrapper.register(self.graph):
48 |             raise RuntimeError(f"Failed to register node '{self.registry_key}' in graph")
   |

src/haywire/core/undo/actions/graph_actions.py:152:100: E501 Line too long (103 > 99)
    |
150 |             description = f"Move {node_count} nodes"
151 |         
152 |         merged = MoveNodesAction(self.graph, self.nodes, combined_deltaX, combined_deltaY, description)
    |                                                                                                    ^^^^ E501
153 |         
154 |         return merged
    |

src/haywire/core/undo/actions/graph_actions.py:191:100: E501 Line too long (107 > 99)
    |
189 |         self.removed_wrappers: Dict[str, NodeWrapper] = {}
190 |         self.removed_edges: Dict[str, Edge] = {}
191 |         self.node_connected_edges: Dict[str, List[Edge]] = {}  # node_id -> edges that were connected to it
    |                                                                                                    ^^^^^^^^ E501
192 |     
193 |     def _execute_impl(self) -> None:
    |

src/haywire/core/undo/history_manager.py:163:100: E501 Line too long (111 > 99)
    |
161 |         if self.config.enable_debug_logging:
162 |             self.logger.debug(f"Added action: {action.description}")
163 |             self.logger.debug(f"History state: {len(self.history)} items, current_index: {self.current_index}")
    |                                                                                                    ^^^^^^^^^^^^ E501
164 |             self.logger.debug(f"Can undo: {self.can_undo()}, Can redo: {self.can_redo()}")
    |

src/haywire/core/undo/history_manager.py:304:100: E501 Line too long (101 > 99)
    |
302 |             return False
303 |         
304 |         last_action = self._pending_actions[-1] if self._pending_actions else self._get_last_action()
    |                                                                                                    ^^ E501
305 |         if not last_action:
306 |             return False
    |

src/haywire/libraries/core/widgets/display_widgets.py:61:100: E501 Line too long (106 > 99)
   |
59 |         return ui.linear_progress(value=normalized_value).classes('w-full').bind_value_from(
60 |             self.data_field, 'value', 
61 |             backward=lambda x: max(0, min(1, (x - min_val) / (max_val - min_val))) if x is not None else 0
   |                                                                                                    ^^^^^^^ E501
62 |         )
   |

src/haywire/ui/editor/event_definitions.py:98:100: E501 Line too long (106 > 99)
    |
 96 |     connections: List[str]
 97 |
 98 | @graph_event("nodeCreateRequest", category="user", description="Request to create node from context menu")
    |                                                                                                    ^^^^^^^ E501
 99 | @dataclass
100 | class NodeCreateRequestEvent(BaseGraphEvent):
    |

src/haywire/ui/editor/event_definitions.py:140:100: E501 Line too long (103 > 99)
    |
138 |     nodeId: str
139 |
140 | @graph_event("contextMenuConnection", category="user", description="Connection context menu triggered")
    |                                                                                                    ^^^^ E501
141 | @dataclass
142 | class ContextMenuConnectionEvent(BaseGraphEvent):
    |

src/haywire/ui/editor/event_definitions.py:149:100: E501 Line too long (111 > 99)
    |
147 |     connectionUUID: str
148 |
149 | @graph_event("contextMenuSelected", category="user", description="Context menu triggered on selected elements")
    |                                                                                                    ^^^^^^^^^^^^ E501
150 | @dataclass
151 | class ContextMenuSelectedEvent(BaseGraphEvent):
    |

src/haywire/ui/editor/event_definitions.py:159:100: E501 Line too long (100 > 99)
    |
157 |     selectedConnections: List[str]
158 |
159 | @graph_event("userCopySelected", category="user", description="Copy selected elements to clipboard")
    |                                                                                                    ^ E501
160 | @dataclass
161 | class UserCopySelectedEvent(BaseGraphEvent):
    |

src/haywire/ui/editor/event_definitions.py:192:100: E501 Line too long (101 > 99)
    |
190 |     position: Dict[str, float]
191 |
192 | @graph_event("syncConnectionAddition", category="sync", description="Sync connection addition to UI")
    |                                                                                                    ^^ E501
193 | @dataclass
194 | class SyncConnectionAdditionEvent(BaseGraphEvent):
    |

src/haywire/ui/editor/event_definitions.py:202:100: E501 Line too long (101 > 99)
    |
200 |     isValid: bool
201 |
202 | @graph_event("syncConnectionRemoval", category="sync", description="Sync connection removal from UI")
    |                                                                                                    ^^ E501
203 | @dataclass
204 | class SyncConnectionRemovalEvent(BaseGraphEvent):
    |

src/haywire/ui/editor/event_generators.py:28:100: E501 Line too long (100 > 99)
   |
26 |                 'description': getattr(event_class, 'description', ''),
27 |                 'fields': [f.name for f in dataclasses.fields(event_class) 
28 |                           if f.name not in ['source_session_id', 'timestamp', 'requires_broadcast']]
   |                                                                                                    ^ E501
29 |             }
   |

src/haywire/ui/editor/event_generators.py:80:100: E501 Line too long (107 > 99)
   |
78 |                 # Add fields (simplified type mapping)
79 |                 for field in fields:
80 |                     field_type = VueEventGenerator._get_typescript_type(field, info.get('field_types', {}))
   |                                                                                                    ^^^^^^^^ E501
81 |                     interface += f'''
82 |   {field}: {field_type};'''
   |

src/haywire/ui/editor/graph_canvas_manager.py:224:101: E501 Line too long (118 > 99)
    |
222 |         """Handle unified element removal"""
223 |         total_elements = len(event.nodes) + len(event.connections)
224 |         print(f"🗑️ Removing {total_elements} elements: {len(event.nodes)} nodes, {len(event.connections)} connections")
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^ E501
225 |         
226 |         # Use the new unified removal method
    |

src/haywire/ui/editor/graph_canvas_manager.py:235:100: E501 Line too long (121 > 99)
    |
233 |     def process_connection_creation(self, event: ConnectionCreatedEvent):
234 |         """Handle connection creation"""
235 |         print(f"Creating connection: {event.outputNodeId}:{event.outletPinId} -> {event.inputNodeId}:{event.inletPinId}")
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^ E501
236 |
237 |         if self.editor.create_connection(
    |

src/haywire/ui/editor/graph_canvas_manager.py:258:100: E501 Line too long (105 > 99)
    |
256 |     def process_selection_change(self, event: SelectionChangedEvent):
257 |         """Handle selection changes"""
258 |         print(f"Selection changed: nodes={event.selectedNodes}, connections={event.selectedConnections}")
    |                                                                                                    ^^^^^^ E501
259 |         
260 |         # Create new selection state
    |

src/haywire/ui/editor/graph_canvas_manager.py:281:100: E501 Line too long (118 > 99)
    |
279 |         self.selected_connections = selected_connections_set
280 |     
281 |     @handles_event(ContextMenuCanvasEvent, ContextMenuNodeEvent, ContextMenuConnectionEvent, ContextMenuSelectedEvent)
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^ E501
282 |     def process_context_menu(self, event):
283 |         """Handle context menu events"""
    |

src/haywire/ui/editor/graph_canvas_manager.py:287:100: E501 Line too long (110 > 99)
    |
285 |             print(f"Canvas context menu at ({event.screenX}, {event.screenY})")
286 |             if self.context_menu:
287 |                 self.context_menu.show_canvas_menu(event.screenX, event.screenY, event.canvasX, event.canvasY)
    |                                                                                                    ^^^^^^^^^^^ E501
288 |             
289 |         elif isinstance(event, ContextMenuNodeEvent):
    |

src/haywire/ui/editor/graph_canvas_manager.py:295:100: E501 Line too long (110 > 99)
    |
294 |         elif isinstance(event, ContextMenuConnectionEvent):
295 |             print(f"Connection context menu for {event.connectionUUID} at ({event.screenX}, {event.screenY})")
    |                                                                                                    ^^^^^^^^^^^ E501
296 |             if self.context_menu:
297 |                 self.context_menu.show_connection_menu(event.screenX, event.screenY, event.connectionUUID)
    |

src/haywire/ui/editor/graph_canvas_manager.py:297:100: E501 Line too long (106 > 99)
    |
295 |             print(f"Connection context menu for {event.connectionUUID} at ({event.screenX}, {event.screenY})")
296 |             if self.context_menu:
297 |                 self.context_menu.show_connection_menu(event.screenX, event.screenY, event.connectionUUID)
    |                                                                                                    ^^^^^^^ E501
298 |         
299 |         elif isinstance(event, ContextMenuSelectedEvent):
    |

src/haywire/ui/editor/graph_canvas_manager.py:300:100: E501 Line too long (164 > 99)
    |
299 | …
300 | …t.screenY}) for {len(event.selectedNodes)} nodes, {len(event.selectedConnections)} connections")
    |                                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
301 | …
302 | …event.screenY, event.selectedNodes, event.selectedConnections)
    |

src/haywire/ui/editor/graph_canvas_manager.py:302:100: E501 Line too long (130 > 99)
    |
300 | …t.screenX}, {event.screenY}) for {len(event.selectedNodes)} nodes, {len(event.selectedConnections)} connections")
301 | …
302 | …u(event.screenX, event.screenY, event.selectedNodes, event.selectedConnections)
    |                                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
303 | …
304 | …
    |

src/haywire/ui/editor/graph_canvas_manager.py:307:99: E501 Line too long (124 > 99)
    |
305 |     def process_node_creation_request(self, event: NodeCreateRequestEvent):
306 |         """Handle node creation requests from context menu or other sources."""
307 |         print(f"📝 Processing node creation request: {event.registryKey} at ({event.position['x']}, {event.position['y']})")
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^ E501
308 |         
309 |         try:
    |

src/haywire/ui/editor/graph_canvas_manager.py:316:99: E501 Line too long (109 > 99)
    |
315 |             if wrapper:
316 |                 print(f"✅ Created node {wrapper.node_id} at ({event.position['x']}, {event.position['y']})")
    |                                                                                                    ^^^^^^^^^^ E501
317 |                 ui.notify(f"Created {event.registryKey} node", type='positive')
318 |             else:
    |

src/haywire/ui/editor/graph_canvas_manager.py:328:99: E501 Line too long (110 > 99)
    |
326 |     def process_copy_selection(self, event: UserCopySelectedEvent):
327 |         """Handle copying selected elements to clipboard."""
328 |         print(f"📋 Copying {len(event.selectedNodes)} nodes and {len(event.selectedConnections)} connections")
    |                                                                                                    ^^^^^^^^^^^ E501
329 |         
330 |         try:
    |

src/haywire/ui/editor/graph_canvas_manager.py:357:99: E501 Line too long (144 > 99)
    |
355 | …
356 | …
357 | …s and {len(self.clipboard.edges)} connections at ({event.canvasX}, {event.canvasY})")
    |                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
358 | …
359 | …
    |

src/haywire/ui/editor/graph_canvas_manager.py:366:100: E501 Line too long (118 > 99)
    |
364 |             for conn_uuid in self.clipboard.edges:
365 |                 edge = self.graph.get_edge(conn_uuid)
366 |                 if edge and edge.output_node_id in self.clipboard.edges and edge.input_node_id in event.selectedNodes:
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^ E501
367 |                     valid_edges.append((conn_uuid, edge))
    |

src/haywire/ui/editor/graph_canvas_manager.py:381:100: E501 Line too long (115 > 99)
    |
379 |                 new_node_id = f"copy_{uuid.uuid4().hex[:8]}_{original_node_id}"
380 |
381 |                 new_node_wrapper = self.graph.create_node_wrapper(registry_key=original_node.identity.registry_key)
    |                                                                                                    ^^^^^^^^^^^^^^^^ E501
382 |                 new_node_wrapper.initialize()
    |

src/haywire/ui/editor/graph_canvas_manager.py:507:99: E501 Line too long (101 > 99)
    |
505 |                 self.remove_connection_visual(connection_uuid)
506 |             
507 |             print(f"🔄 Incremental connection sync: {len(graph_connection_uuids)} total connections")
    |                                                                                                    ^^ E501
508 |             
509 |             # Sync selection state from graph to UI
    |

src/haywire/ui/editor/graph_canvas_manager.py:524:99: E501 Line too long (134 > 99)
    |
522 | …
523 | …
524 | …en(graph_selected_nodes)} nodes, {len(graph_selected_connections)} connections")
    |                                               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
525 | …
526 | …
    |

src/haywire/ui/editor/graph_canvas_manager.py:623:99: E501 Line too long (144 > 99)
    |
621 | …
622 | …
623 | …ge.output_node_id}:{edge.outlet_pin_id} -> {edge.input_node_id}:{edge.inlet_pin_id}")
    |                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
624 | …
625 | …
    |

src/haywire/ui/editor/node_menu_builder.py:2:100: E501 Line too long (118 > 99)
  |
1 | """
2 | NodeMenuBuilder - Creates hierarchical NiceGUI menus fro                # Create "Add Nodes" button with complete menu
  |                                                                                                    ^^^^^^^^^^^^^^^^^^^ E501
3 |                 with ui.button("➕ Add Nodes").props('flat') \
4 |                     .classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm'):
  |

src/haywire/ui/editor/node_menu_builder.py:4:100: E501 Line too long (122 > 99)
  |
2 | NodeMenuBuilder - Creates hierarchical NiceGUI menus fro                # Create "Add Nodes" button with complete menu
3 |                 with ui.button("➕ Add Nodes").props('flat') \
4 |                     .classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm'):
  |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^ E501
5 |                     with ui.menu() as main_menu:
6 |                         # Add recent nodes section if provided
  |

src/haywire/ui/editor/node_menu_builder.py:115:100: E501 Line too long (109 > 99)
    |
113 |                 ui.label('No nodes found').classes('text-gray-500 text-sm p-2')
114 |             else:
115 |                 ui.label(f'Found {len(results)} node(s)').classes('text-xs font-semibold text-gray-600 mb-2')
    |                                                                                                    ^^^^^^^^^^ E501
116 |                 
117 |                 for node_info in results[:10]:  # Limit to 10 results
    |

src/haywire/ui/editor/node_menu_builder.py:129:100: E501 Line too long (112 > 99)
    |
127 |         )
128 |         btn.props('flat align=left')
129 |         btn.classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm')
    |                                                                                                    ^^^^^^^^^^^^^ E501
130 |         
131 |         # Add library badge
    |

src/haywire/ui/editor/node_menu_builder.py:140:100: E501 Line too long (106 > 99)
    |
138 |         btn.tooltip(tooltip_text)
139 |     
140 |     def _add_recent_nodes_section(self, recent_nodes: List[str], on_node_selected: Callable[[str], None]):
    |                                                                                                    ^^^^^^^ E501
141 |         """Add section for recently created nodes using native menu with hover functionality."""
142 |         if not recent_nodes:
    |

src/haywire/ui/editor/node_menu_builder.py:212:100: E501 Line too long (109 > 99)
    |
210 |         return tree
211 |     
212 |     def _create_menu_tree_ui(self, menu_tree: Dict, on_node_selected: Callable[[str], None], level: int = 0):
    |                                                                                                    ^^^^^^^^^^ E501
213 |         """Create UI elements for the menu tree using native ui.menu components."""
214 |         for category_name, category_data in sorted(menu_tree.items()):
    |

src/haywire/ui/editor/node_menu_builder.py:232:100: E501 Line too long (138 > 99)
    |
230 | …y_name, nodes, on_node_selected)
231 | …
232 | …: str, nodes: List[Dict], children: Dict, on_node_selected: Callable[[str], None]):
    |                                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
233 | …t nodes and subcategories with hover functionality."""
234 | …ose=False) as menu_item:
    |

src/haywire/ui/editor/node_menu_builder.py:233:100: E501 Line too long (109 > 99)
    |
232 |     def _create_mixed_category_menu(self, category_name: str, nodes: List[Dict], children: Dict, on_node_selected: Callable[[str], No…
233 |         """Create menu for category that has both direct nodes and subcategories with hover functionality."""
    |                                                                                                    ^^^^^^^^^^ E501
234 |         with ui.menu_item(f"📁 {category_name}", auto_close=False) as menu_item:
235 |             with ui.item_section().props('side'):
    |

src/haywire/ui/editor/node_menu_builder.py:257:100: E501 Line too long (116 > 99)
    |
255 |             self._add_hover_behavior(menu_item, submenu)
256 |
257 |     def _create_submenu_category(self, category_name: str, children: Dict, on_node_selected: Callable[[str], None]):
    |                                                                                                    ^^^^^^^^^^^^^^^^^ E501
258 |         """Create menu for category that only has subcategories with hover functionality."""
259 |         with ui.menu_item(f"📁 {category_name}", auto_close=False) as menu_item:
    |

src/haywire/ui/editor/node_menu_builder.py:272:100: E501 Line too long (121 > 99)
    |
270 |             self._add_hover_behavior(menu_item, submenu)
271 |
272 |     def _create_leaf_category_menu(self, category_name: str, nodes: List[Dict], on_node_selected: Callable[[str], None]):
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^ E501
273 |         """Create menu for category that only has direct nodes with hover functionality."""
274 |         with ui.menu_item(f"📁 {category_name}", auto_close=False) as menu_item:
    |

src/haywire/ui/editor/node_menu_builder.py:287:100: E501 Line too long (113 > 99)
    |
285 |             self._add_hover_behavior(menu_item, submenu)
286 |
287 |     def _create_submenu_item(self, subcat_name: str, subcat_data: Dict, on_node_selected: Callable[[str], None]):
    |                                                                                                    ^^^^^^^^^^^^^^ E501
288 |         """Create a submenu item for a subcategory with hover functionality."""
289 |         subnodes = subcat_data.get('_nodes', [])
    |

src/haywire/ui/editor/node_menu_builder.py:317:100: E501 Line too long (109 > 99)
    |
315 |             self._add_hover_behavior(menu_item, submenu)
316 |
317 |     def _create_menu_item_for_node(self, node_info: Dict[str, str], on_node_selected: Callable[[str], None]):
    |                                                                                                    ^^^^^^^^^^ E501
318 |         """Create a menu item for a single node."""
319 |         # Get the correct key field
    |

src/haywire/ui/editor/node_menu_builder.py:391:100: E501 Line too long (102 > 99)
    |
389 |         return lambda: asyncio.create_task(close_all_submenus())
390 |
391 |     def _create_node_button(self, node_info: Dict[str, str], on_node_selected: Callable[[str], None]):
    |                                                                                                    ^^^ E501
392 |         """Create a button for a single node (used in recent nodes section)."""
393 |         # Get the correct key field
    |

src/haywire/ui/editor/node_menu_builder.py:401:100: E501 Line too long (112 > 99)
    |
399 |         )
400 |         btn.props('flat align=left')
401 |         btn.classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm')
    |                                                                                                    ^^^^^^^^^^^^^ E501
402 |         
403 |         # Add tooltip with description and tags if available
    |

src/haywire/ui/editor/popup.py:164:100: E501 Line too long (100 > 99)
    |
163 |                         if self.closable:
164 |                             ui.button(icon='close', on_click=self.close).props('flat round size=sm')
    |                                                                                                    ^ E501
165 |                     
166 |                     if self.title:  # Only add separator if there's a title
    |

src/haywire/ui/editor/popup_context_menu.py:9:100: E501 Line too long (107 > 99)
   |
 7 | - Connections: Connection operations menu when Ctrl+clicking on connections
 8 |
 9 | Uses the enhanced Popup class that creates elements at page root level to avoid zoom/transform inheritance.
   |                                                                                                    ^^^^^^^^ E501
10 | """
   |

src/haywire/ui/editor/popup_context_menu.py:18:100: E501 Line too long (119 > 99)
   |
17 | from .popup import Popup
18 | from .event_definitions import  NodeCreateRequestEvent, UserRemoveEvent, UserCopySelectedEvent, UserPasteClipboardEvent
   |                                                                                                    ^^^^^^^^^^^^^^^^^^^^ E501
19 | from .node_menu_builder import NodeMenuBuilder
   |

src/haywire/ui/editor/popup_context_menu.py:160:100: E501 Line too long (130 > 99)
    |
158 |                     btn_paste = ui.button('📄 Paste', on_click=lambda: self._paste_clipboard())
159 |                     btn_paste.props('flat align=left')
160 |                     btn_paste.classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm')
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
161 |                     
162 |                     # Add separator if we have paste option
    |

src/haywire/ui/editor/popup_context_menu.py:193:99: E501 Line too long (101 > 99)
    |
191 |         with popup:
192 |             with ui.column().classes('w-full gap-1'):
193 |                 btn1 = ui.button('📋 Duplicate Node', on_click=lambda: self._duplicate_node(node_id))
    |                                                                                                    ^^ E501
194 |                 btn1.props('flat align=left')
195 |                 btn1.classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm')
    |

src/haywire/ui/editor/popup_context_menu.py:195:100: E501 Line too long (121 > 99)
    |
193 |                 btn1 = ui.button('📋 Duplicate Node', on_click=lambda: self._duplicate_node(node_id))
194 |                 btn1.props('flat align=left')
195 |                 btn1.classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm')
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^ E501
196 |                 
197 |                 btn2 = ui.button('📄 Copy Node', on_click=lambda: self._copy_node(node_id))
    |

src/haywire/ui/editor/popup_context_menu.py:199:100: E501 Line too long (121 > 99)
    |
197 |                 btn2 = ui.button('📄 Copy Node', on_click=lambda: self._copy_node(node_id))
198 |                 btn2.props('flat align=left')
199 |                 btn2.classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm')
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^ E501
200 |                 
201 |                 btn3 = ui.button('🗑️ Delete Node', on_click=lambda: self._delete_node(node_id))
    |

src/haywire/ui/editor/popup_context_menu.py:203:100: E501 Line too long (118 > 99)
    |
201 |                 btn3 = ui.button('🗑️ Delete Node', on_click=lambda: self._delete_node(node_id))
202 |                 btn3.props('flat align=left')
203 |                 btn3.classes('w-full justify-start px-3 py-2 text-red-600 hover:bg-red-50 hover:text-red-700 text-sm')
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^ E501
204 |         
205 |         popup.open()
    |

src/haywire/ui/editor/popup_context_menu.py:220:99: E501 Line too long (115 > 99)
    |
218 |         with popup:
219 |             with ui.column().classes('w-full gap-1'):
220 |                 btn1 = ui.button('🔍 Inspect Connection', on_click=lambda: self._inspect_connection(connection_id))
    |                                                                                                    ^^^^^^^^^^^^^^^^ E501
221 |                 btn1.props('flat align=left')
222 |                 btn1.classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm')
    |

src/haywire/ui/editor/popup_context_menu.py:222:100: E501 Line too long (121 > 99)
    |
220 |                 btn1 = ui.button('🔍 Inspect Connection', on_click=lambda: self._inspect_connection(connection_id))
221 |                 btn1.props('flat align=left')
222 |                 btn1.classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm')
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^ E501
223 |                 
224 |                 btn2 = ui.button('🗑️ Delete Connection', on_click=lambda: self._delete_connection(connection_id))
    |

src/haywire/ui/editor/popup_context_menu.py:224:101: E501 Line too long (112 > 99)
    |
222 |                 btn1.classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm')
223 |                 
224 |                 btn2 = ui.button('🗑️ Delete Connection', on_click=lambda: self._delete_connection(connection_id))
    |                                                                                                    ^^^^^^^^^^^^^ E501
225 |                 btn2.props('flat align=left')
226 |                 btn2.classes('w-full justify-start px-3 py-2 text-red-600 hover:bg-red-50 hover:text-red-700 text-sm')
    |

src/haywire/ui/editor/popup_context_menu.py:226:100: E501 Line too long (118 > 99)
    |
224 |                 btn2 = ui.button('🗑️ Delete Connection', on_click=lambda: self._delete_connection(connection_id))
225 |                 btn2.props('flat align=left')
226 |                 btn2.classes('w-full justify-start px-3 py-2 text-red-600 hover:bg-red-50 hover:text-red-700 text-sm')
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^ E501
227 |         
228 |         popup.open()
    |

src/haywire/ui/editor/popup_context_menu.py:231:100: E501 Line too long (113 > 99)
    |
229 |         self._current_popup = popup
230 |     
231 |     def show_selected_menu(self, x: float, y: float, selected_nodes: List[str], selected_connections: List[str]):
    |                                                                                                    ^^^^^^^^^^^^^^ E501
232 |         """Show context menu for multi-selection operations."""
233 |         self._close_current_menu()
    |

src/haywire/ui/editor/popup_context_menu.py:250:100: E501 Line too long (112 > 99)
    |
248 |             title = f"Selection ({node_count} {'node' if node_count == 1 else 'nodes'})"
249 |         elif connection_count > 0:
250 |             title = f"Selection ({connection_count} {'connection' if connection_count == 1 else 'connections'})"
    |                                                                                                    ^^^^^^^^^^^^^ E501
251 |         else:
252 |             title = "Selection"
    |

src/haywire/ui/editor/popup_context_menu.py:263:100: E501 Line too long (122 > 99)
    |
261 |                     btn1 = ui.button('🗑️ Delete Selected', on_click=lambda: self._delete_selected())
262 |                     btn1.props('flat align=left')
263 |                     btn1.classes('w-full justify-start px-3 py-2 text-red-600 hover:bg-red-50 hover:text-red-700 text-sm')
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^ E501
264 |                 
265 |                 # Group selected (placeholder - not implemented yet)
    |

src/haywire/ui/editor/popup_context_menu.py:267:99: E501 Line too long (101 > 99)
    |
265 |                 # Group selected (placeholder - not implemented yet)
266 |                 if node_count > 1:
267 |                     btn2 = ui.button('📦 Group Nodes', on_click=lambda: self._group_selected_nodes())
    |                                                                                                    ^^ E501
268 |                     btn2.props('flat align=left')
269 |                     btn2.classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm')
    |

src/haywire/ui/editor/popup_context_menu.py:269:100: E501 Line too long (125 > 99)
    |
267 |                     btn2 = ui.button('📦 Group Nodes', on_click=lambda: self._group_selected_nodes())
268 |                     btn2.props('flat align=left')
269 |                     btn2.classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm')
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
270 |                 
271 |                 # Copy selected (placeholder - not implemented yet)
    |

src/haywire/ui/editor/popup_context_menu.py:273:99: E501 Line too long (102 > 99)
    |
271 |                 # Copy selected (placeholder - not implemented yet)
272 |                 if node_count > 0:
273 |                     btn3 = ui.button('📋 Copy Selected', on_click=lambda: self._copy_selected_nodes())
    |                                                                                                    ^^^ E501
274 |                     btn3.props('flat align=left')
275 |                     btn3.classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm')
    |

src/haywire/ui/editor/popup_context_menu.py:275:100: E501 Line too long (125 > 99)
    |
273 |                     btn3 = ui.button('📋 Copy Selected', on_click=lambda: self._copy_selected_nodes())
274 |                     btn3.props('flat align=left')
275 |                     btn3.classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm')
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
276 |         
277 |         popup.open()
    |

src/haywire/ui/errors/error_info.py:69:100: E501 Line too long (108 > 99)
   |
67 |                 # Footer with close button
68 |                 with ui.row().classes('justify-end w-full pt-3 border-t mt-4'):
69 |                     ui.button('Close', icon='close', on_click=close_popup).classes('bg-gray-600 text-white')
   |                                                                                                    ^^^^^^^^^ E501
70 |         
71 |         # Register cleanup callback when popup is closed via other means
   |

src/haywire/ui/errors/error_info.py:85:100: E501 Line too long (100 > 99)
   |
83 |             with ui.row().classes('items-start gap-3 w-full'):
84 |                 # Icon
85 |                 detail_button = ui.button(icon='bug_report').classes('w-full bg-red-600 text-white')
   |                                                                                                    ^ E501
86 |         
87 |         # Connect button to show details
   |

src/haywire/ui/errors/haywire_exception.py:8:100: E501 Line too long (108 > 99)
   |
 6 | from haywire.ui.utils import _open_file_in_editor
 7 |
 8 | def _create_detail_row(label: str, value: str, icon: str, multiline: bool = False, monospace: bool = False, 
   |                                                                                                    ^^^^^^^^^ E501
 9 |                        file_path: str = None, line_number: int = None):
10 |     """Helper to create a consistent detail row with optional file open button"""
   |

src/haywire/ui/errors/haywire_exception.py:35:100: E501 Line too long (115 > 99)
   |
33 |                         ui.button(
34 |                             icon='content_copy',
35 |                             on_click=lambda p=file_path: ui.run_javascript(f'navigator.clipboard.writeText({p!r})')
   |                                                                                                    ^^^^^^^^^^^^^^^^ E501
36 |                         ).props('flat dense size=sm').tooltip('Copy file path')
   |

src/haywire/ui/errors/haywire_exception.py:59:100: E501 Line too long (100 > 99)
   |
57 |         # Header
58 |         with ui.row().classes('items-center gap-2 pb-3 border-b'):
59 |             ui.icon(error.get_severity_icon(), color=error.get_severity_color()).classes('text-3xl')
   |                                                                                                    ^ E501
60 |             ui.label(f"{error.category}").classes('text-xl font-bold text-gray-800')
61 |             ui.button(
   |

src/haywire/ui/errors/haywire_exception.py:89:100: E501 Line too long (102 > 99)
   |
87 |                         with ui.column().classes('mt-2'):
88 |                             code_lines = [line_content for _, line_content in error.source_context]
89 |                             first_line_num = error.source_context[0][0] if error.source_context else 1
   |                                                                                                    ^^^ E501
90 |
91 |                             # Detect language from filename extension
   |

src/haywire/ui/errors/haywire_exception.py:122:100: E501 Line too long (123 > 99)
    |
120 | …                         exc_message = str(error.original_exception)
121 | …                         numbered_lines.append(f"{'':>{line_num_width}} ")
122 | …                         numbered_lines.append(f"{'':>{line_num_width}} -> {exc_type_name}: {exc_message} ")
    |                                                                                      ^^^^^^^^^^^^^^^^^^^^^^^^ E501
123 | …                     numbered_lines.append(f"{'':>{line_num_width}} ")
124 | …                     numbered_lines.append(f"{line_num:>{line_num_width}} >> {line}  <<")
    |

src/haywire/ui/errors/haywire_exception.py:124:100: E501 Line too long (104 > 99)
    |
122 | …                             numbered_lines.append(f"{'':>{line_num_width}} -> {exc_type_name}: {exc_message} ")
123 | …                         numbered_lines.append(f"{'':>{line_num_width}} ")
124 | …                         numbered_lines.append(f"{line_num:>{line_num_width}} >> {line}  <<")
    |                                                                                          ^^^^^ E501
125 | …                         numbered_lines.append(f"{'':>{line_num_width}} ")
126 | …                     else:
    |

src/haywire/ui/errors/haywire_exception.py:127:100: E501 Line too long (100 > 99)
    |
125 | …                             numbered_lines.append(f"{'':>{line_num_width}} ")
126 | …                         else:
127 | …                             numbered_lines.append(f"{line_num:>{line_num_width}}  : {line}")
    |                                                                                              ^ E501
128 | …                     
129 | …                     code_with_numbers = '\n'.join(numbered_lines)
    |

src/haywire/ui/errors/haywire_exception.py:138:100: E501 Line too long (114 > 99)
    |
136 | …                     if error.library_identity and error.library_identity.folder_path:
137 | …                         try:
138 | …                             rel_path = os.path.relpath(error.filename, error.library_identity.folder_path)
    |                                                                                              ^^^^^^^^^^^^^^^ E501
139 | …                             if not rel_path.startswith(".."):
140 | …                                 file_display = f"./{rel_path}"
    |

src/haywire/ui/errors/haywire_exception.py:144:100: E501 Line too long (100 > 99)
    |
142 |                                     pass
143 |
144 |                             _create_detail_row('File', file_display, 'description', monospace=True, 
    |                                                                                                    ^ E501
145 |                                              file_path=error.filename, line_number=error.line_number)
    |

src/haywire/ui/errors/haywire_exception.py:145:100: E501 Line too long (101 > 99)
    |
144 |                             _create_detail_row('File', file_display, 'description', monospace=True, 
145 |                                              file_path=error.filename, line_number=error.line_number)
    |                                                                                                    ^^ E501
146 |
147 |                             if error.line_number:
    |

src/haywire/ui/errors/haywire_exception.py:152:100: E501 Line too long (101 > 99)
    |
150 |         # Traceback section (filter interesting frames)
151 |         if error.traceback_frames:
152 |             interesting_frames = [f for f in error.traceback_frames if error.is_interesting_frame(f)]
    |                                                                                                    ^^ E501
153 |
154 |             if interesting_frames:
    |

src/haywire/ui/errors/haywire_exception.py:168:100: E501 Line too long (103 > 99)
    |
166 |                                 base_filename = os.path.basename(filename)
167 |
168 |                                 with ui.column().classes('gap-1 border-l-2 border-blue-300 pl-3 py-1'):
    |                                                                                                    ^^^^ E501
169 |                                     # Location with Open button
170 |                                     with ui.row().classes('items-center gap-2'):
    |

src/haywire/ui/errors/haywire_exception.py:173:100: E501 Line too long (104 > 99)
    |
171 | …                     ui.icon('arrow_right', color='blue').classes('text-sm')
172 | …                     ui.label(f"{base_filename}").classes('font-bold text-sm')
173 | …                     ui.label(f"in {function_name}").classes('text-sm text-gray-600')
    |                                                                                  ^^^^^ E501
174 | …                     # Add open button for each frame
175 | …                     if os.path.exists(filename):
    |

src/haywire/ui/errors/haywire_exception.py:178:100: E501 Line too long (119 > 99)
    |
176 | …                     ui.button(
177 | …                         icon='open_in_new',
178 | …                         on_click=lambda f=filename, ln=line_number: _open_file_in_editor(f, ln)
    |                                                                              ^^^^^^^^^^^^^^^^^^^^ E501
179 | …                     ).props('flat dense size=xs').tooltip('Open in editor')
    |

src/haywire/ui/errors/haywire_exception.py:185:100: E501 Line too long (113 > 99)
    |
183 |                                     if len(display_path) > 60:
184 |                                         display_path = '...' + display_path[-57:]
185 |                                     ui.label(f'File "{display_path}"').classes('text-xs text-gray-500 font-mono')
    |                                                                                                    ^^^^^^^^^^^^^^ E501
186 |
187 |                                     # Source line
    |

src/haywire/ui/errors/haywire_exception.py:189:100: E501 Line too long (112 > 99)
    |
187 | …                     # Source line
188 | …                     if source_line.strip():
189 | …                         with ui.row().classes('items-start gap-2 mt-1 bg-gray-100 rounded p-2'):
    |                                                                                      ^^^^^^^^^^^^^ E501
190 | …                             ui.label(f"line {line_number}:").classes('text-xs text-blue-600 font-mono')
191 | …                             ui.label(source_line.strip()).classes('text-xs font-mono')
    |

src/haywire/ui/errors/haywire_exception.py:190:100: E501 Line too long (119 > 99)
    |
188 | …                     if source_line.strip():
189 | …                         with ui.row().classes('items-start gap-2 mt-1 bg-gray-100 rounded p-2'):
190 | …                             ui.label(f"line {line_number}:").classes('text-xs text-blue-600 font-mono')
    |                                                                                      ^^^^^^^^^^^^^^^^^^^^ E501
191 | …                             ui.label(source_line.strip()).classes('text-xs font-mono')
    |

src/haywire/ui/errors/haywire_exception.py:191:100: E501 Line too long (102 > 99)
    |
189 |                                         with ui.row().classes('items-start gap-2 mt-1 bg-gray-100 rounded p-2'):
190 |                                             ui.label(f"line {line_number}:").classes('text-xs text-blue-600 font-mono')
191 |                                             ui.label(source_line.strip()).classes('text-xs font-mono')
    |                                                                                                    ^^^ E501
192 |
193 |         # Show the actual error message right above the code
    |

src/haywire/ui/errors/haywire_exception.py:213:100: E501 Line too long (107 > 99)
    |
212 |                 if error.severity:
213 |                     _create_detail_row('Severity', error.severity.value.upper(), error.get_severity_icon())
    |                                                                                                    ^^^^^^^^ E501
214 |
215 |                 if error.context_type:
    |

src/haywire/ui/errors/haywire_exception.py:230:100: E501 Line too long (121 > 99)
    |
228 |                         _create_detail_row('Library', error.library_identity.label, 'folder')
229 |                         if error.library_identity.folder_path:
230 |                             _create_detail_row('Path', error.library_identity.folder_path, 'folder_open', monospace=True)
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^ E501
231 |
232 |                     if error.registry_key:
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:110:100: E501 Line too long (106 > 99)
    |
109 |             # Toggle button
110 |             self.toggle_btn = ui.button('×', on_click=self.toggle_visibility).props('round dense size=xs')
    |                                                                                                    ^^^^^^^ E501
111 |             self.toggle_btn.style('position: absolute; top: -8px; right: -8px; width: 16px; height: 16px; min-width: 16px;')
112 |             self.toggle_btn.classes('bg-gray-600 text-white text-xs')
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:111:100: E501 Line too long (124 > 99)
    |
109 |             # Toggle button
110 |             self.toggle_btn = ui.button('×', on_click=self.toggle_visibility).props('round dense size=xs')
111 |             self.toggle_btn.style('position: absolute; top: -8px; right: -8px; width: 16px; height: 16px; min-width: 16px;')
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^ E501
112 |             self.toggle_btn.classes('bg-gray-600 text-white text-xs')
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:145:100: E501 Line too long (104 > 99)
    |
143 |                     retryCount++;
144 |                     
145 |                     const mainContainer = document.getElementById('{self.zoom_container.container_id}');
    |                                                                                                    ^^^^^ E501
146 |                     const minimap = document.getElementById('{self.minimap_id}');
147 |                     const canvas = document.getElementById('{self.canvas_id}');
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:207:100: E501 Line too long (101 > 99)
    |
205 |                         scaleFactor = Math.min(scaleX, scaleY, 1.0); // Don't scale up
206 |                         
207 |                         console.log('Content bounds updated:', bounds, 'Scale factor:', scaleFactor);
    |                                                                                                    ^^ E501
208 |                         drawMinimap();
209 |                     }}
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:227:100: E501 Line too long (102 > 99)
    |
226 |                         // Convert content coordinates to minimap pixel coordinates
227 |                         const minimapX = MINIMAP_PADDING + (viewX - contentBounds.minX) * scaleFactor;
    |                                                                                                    ^^^ E501
228 |                         const minimapY = MINIMAP_PADDING + (viewY - contentBounds.minY) * scaleFactor;
229 |                         const minimapWidth = Math.max(2, viewWidth * scaleFactor);
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:228:100: E501 Line too long (102 > 99)
    |
226 |                         // Convert content coordinates to minimap pixel coordinates
227 |                         const minimapX = MINIMAP_PADDING + (viewX - contentBounds.minX) * scaleFactor;
228 |                         const minimapY = MINIMAP_PADDING + (viewY - contentBounds.minY) * scaleFactor;
    |                                                                                                    ^^^ E501
229 |                         const minimapWidth = Math.max(2, viewWidth * scaleFactor);
230 |                         const minimapHeight = Math.max(2, viewHeight * scaleFactor);
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:252:100: E501 Line too long (100 > 99)
    |
250 |                         const boundsX = MINIMAP_PADDING;
251 |                         const boundsY = MINIMAP_PADDING;
252 |                         const boundsWidth = (contentBounds.maxX - contentBounds.minX) * scaleFactor;
    |                                                                                                    ^ E501
253 |                         const boundsHeight = (contentBounds.maxY - contentBounds.minY) * scaleFactor;
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:253:100: E501 Line too long (101 > 99)
    |
251 |                         const boundsY = MINIMAP_PADDING;
252 |                         const boundsWidth = (contentBounds.maxX - contentBounds.minX) * scaleFactor;
253 |                         const boundsHeight = (contentBounds.maxY - contentBounds.minY) * scaleFactor;
    |                                                                                                    ^^ E501
254 |                         
255 |                         // Content area background
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:271:100: E501 Line too long (119 > 99)
    |
269 |                         for (let x = boundsX; x < boundsX + boundsWidth; x += gridSpacing) {{
270 |                             for (let y = boundsY; y < boundsY + boundsHeight; y += gridSpacing) {{
271 |                                 if (x + gridSize <= boundsX + boundsWidth && y + gridSize <= boundsY + boundsHeight) {{
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^ E501
272 |                                     ctx.fillRect(x, y, gridSize, gridSize);
273 |                                 }}
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:285:100: E501 Line too long (113 > 99)
    |
283 |                         const clampedX = Math.max(0, Math.min(viewportRect.x, minimap_width));
284 |                         const clampedY = Math.max(0, Math.min(viewportRect.y, minimap_height));
285 |                         const clampedWidth = Math.max(1, Math.min(viewportRect.width, minimap_width - clampedX));
    |                                                                                                    ^^^^^^^^^^^^^^ E501
286 |                         const clampedHeight = Math.max(1, Math.min(viewportRect.height, minimap_height - clampedY));
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:286:100: E501 Line too long (116 > 99)
    |
284 |                         const clampedY = Math.max(0, Math.min(viewportRect.y, minimap_height));
285 |                         const clampedWidth = Math.max(1, Math.min(viewportRect.width, minimap_width - clampedX));
286 |                         const clampedHeight = Math.max(1, Math.min(viewportRect.height, minimap_height - clampedY));
    |                                                                                                    ^^^^^^^^^^^^^^^^^ E501
287 |                         
288 |                         ctx.fillRect(clampedX, clampedY, clampedWidth, clampedHeight);
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:294:100: E501 Line too long (112 > 99)
    |
292 |                         ctx.fillStyle = 'black';
293 |                         ctx.font = '10px monospace';
294 |                         ctx.fillText(`Minimap: ${{minimap_width}}x${{minimap_height}}`, 5, minimap_height - 65);
    |                                                                                                    ^^^^^^^^^^^^^ E501
295 |                         ctx.fillText(`Content: ${{contentWidth.toFixed(0)}}x${{contentHeight.toFixed(0)}}`, 5, minimap_height - 55);
296 |                         ctx.fillText(`Pan: ${{panX.toFixed(0)}}x${{panY.toFixed(0)}}`, 5, minimap_height - 45);
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:295:100: E501 Line too long (132 > 99)
    |
293 |                         ctx.font = '10px monospace';
294 |                         ctx.fillText(`Minimap: ${{minimap_width}}x${{minimap_height}}`, 5, minimap_height - 65);
295 |                         ctx.fillText(`Content: ${{contentWidth.toFixed(0)}}x${{contentHeight.toFixed(0)}}`, 5, minimap_height - 55);
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
296 |                         ctx.fillText(`Pan: ${{panX.toFixed(0)}}x${{panY.toFixed(0)}}`, 5, minimap_height - 45);
297 |                         ctx.fillText(`Zoom: ${{zoom.toFixed(3)}}`, 5, minimap_height - 35);
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:296:100: E501 Line too long (111 > 99)
    |
294 |                         ctx.fillText(`Minimap: ${{minimap_width}}x${{minimap_height}}`, 5, minimap_height - 65);
295 |                         ctx.fillText(`Content: ${{contentWidth.toFixed(0)}}x${{contentHeight.toFixed(0)}}`, 5, minimap_height - 55);
296 |                         ctx.fillText(`Pan: ${{panX.toFixed(0)}}x${{panY.toFixed(0)}}`, 5, minimap_height - 45);
    |                                                                                                    ^^^^^^^^^^^^ E501
297 |                         ctx.fillText(`Zoom: ${{zoom.toFixed(3)}}`, 5, minimap_height - 35);
298 |                         ctx.fillText(`Scale: ${{scaleFactor.toFixed(3)}}`, 5, minimap_height - 25);
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:299:100: E501 Line too long (131 > 99)
    |
297 |                         ctx.fillText(`Zoom: ${{zoom.toFixed(3)}}`, 5, minimap_height - 35);
298 |                         ctx.fillText(`Scale: ${{scaleFactor.toFixed(3)}}`, 5, minimap_height - 25);
299 |                         ctx.fillText(`Bounds: ${{Math.round(boundsWidth)}}x${{Math.round(boundsHeight)}}`, 5, minimap_height - 15);
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
300 |                         ctx.fillText(`View: ${{Math.round(clampedWidth)}}x${{Math.round(clampedHeight)}}`, 5, minimap_height - 5);
301 |                     }}
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:300:100: E501 Line too long (130 > 99)
    |
298 |                         ctx.fillText(`Scale: ${{scaleFactor.toFixed(3)}}`, 5, minimap_height - 25);
299 |                         ctx.fillText(`Bounds: ${{Math.round(boundsWidth)}}x${{Math.round(boundsHeight)}}`, 5, minimap_height - 15);
300 |                         ctx.fillText(`View: ${{Math.round(clampedWidth)}}x${{Math.round(clampedHeight)}}`, 5, minimap_height - 5);
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
301 |                     }}
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:304:100: E501 Line too long (105 > 99)
    |
303 |                     function minimapToContent(minimapX, minimapY) {{
304 |                         const contentX = contentBounds.minX + (minimapX - MINIMAP_PADDING) / scaleFactor;
    |                                                                                                    ^^^^^^ E501
305 |                         const contentY = contentBounds.minY + (minimapY - MINIMAP_PADDING) / scaleFactor;
306 |                         return {{ x: contentX, y: contentY }};
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:305:100: E501 Line too long (105 > 99)
    |
303 |                     function minimapToContent(minimapX, minimapY) {{
304 |                         const contentX = contentBounds.minX + (minimapX - MINIMAP_PADDING) / scaleFactor;
305 |                         const contentY = contentBounds.minY + (minimapY - MINIMAP_PADDING) / scaleFactor;
    |                                                                                                    ^^^^^^ E501
306 |                         return {{ x: contentX, y: contentY }};
307 |                     }}
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:322:100: E501 Line too long (100 > 99)
    |
321 | …                     // Calculate new pan to center clicked point
322 | …                     const newPanX = -(contentPos.x * currentZoom - containerRect.width / 2);
    |                                                                                              ^ E501
323 | …                     const newPanY = -(contentPos.y * currentZoom - containerRect.height / 2);
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:323:100: E501 Line too long (101 > 99)
    |
321 | …                     // Calculate new pan to center clicked point
322 | …                     const newPanX = -(contentPos.x * currentZoom - containerRect.width / 2);
323 | …                     const newPanY = -(contentPos.y * currentZoom - containerRect.height / 2);
    |                                                                                              ^^ E501
324 | …                     
325 | …                     mainContainer._zoomPanControls.setPan(newPanX, newPanY);
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:452:100: E501 Line too long (117 > 99)
    |
451 |                 // Get all meaningful content elements
452 |                 const elements = content.querySelectorAll('.zoomable-card, .card, [class*="card"], [class*="item"]');
    |                                                                                                    ^^^^^^^^^^^^^^^^^^ E501
453 |                 
454 |                 let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:534:100: E501 Line too long (106 > 99)
    |
532 |             const mainContainer = document.getElementById('{self.zoom_container.container_id}');
533 |             
534 |             if (minimap && minimap._minimapControls && mainContainer && mainContainer._zoomPanControls) {{
    |                                                                                                    ^^^^^^^ E501
535 |                 const currentZoom = mainContainer._zoomPanControls.getZoom();
536 |                 const currentPan = mainContainer._zoomPanControls.getPan();
    |

src/haywire/ui/pan_zoom/mini_map_vue.py:571:100: E501 Line too long (105 > 99)
    |
569 |                 minimap.style.bottom = 'auto';
570 |                 minimap.style.left = 'auto';
571 |                 minimap.style.cssText += '{position_styles.get(position, position_styles["top-right"])}';
    |                                                                                                    ^^^^^^ E501
572 |             }}
573 |         ''')
    |

src/haywire/ui/pan_zoom/minimap.py:85:100: E501 Line too long (115 > 99)
   |
83 |         with self:
84 |             self.canvas = ui.element('canvas')
85 |             self.canvas.props(f'id="{self.canvas_id}" width="{self.minimap_width}" height="{self.minimap_height}"')
   |                                                                                                    ^^^^^^^^^^^^^^^^ E501
86 |             self.canvas.style('display: block; width: 100%; height: 100%;')
   |

src/haywire/ui/pan_zoom/minimap.py:88:100: E501 Line too long (106 > 99)
   |
86 |             self.canvas.style('display: block; width: 100%; height: 100%;')
87 |             
88 |             self.toggle_btn = ui.button('×', on_click=self.toggle_visibility).props('round dense size=xs')
   |                                                                                                    ^^^^^^^ E501
89 |             self.toggle_btn.style('position: absolute; top: -8px; right: -8px; width: 16px; height: 16px; min-width: 16px;')
90 |             self.toggle_btn.classes('bg-gray-600 text-white text-xs')
   |

src/haywire/ui/pan_zoom/minimap.py:89:100: E501 Line too long (124 > 99)
   |
88 |             self.toggle_btn = ui.button('×', on_click=self.toggle_visibility).props('round dense size=xs')
89 |             self.toggle_btn.style('position: absolute; top: -8px; right: -8px; width: 16px; height: 16px; min-width: 16px;')
   |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^ E501
90 |             self.toggle_btn.classes('bg-gray-600 text-white text-xs')
   |

src/haywire/ui/pan_zoom/minimap.py:150:100: E501 Line too long (104 > 99)
    |
149 |                 function updateViewport(zoom, panX, panY) {{
150 |                     const mainContainer = document.getElementById('{self.zoom_container.container_id}');
    |                                                                                                    ^^^^^ E501
151 |                     if (!mainContainer) return;
    |

src/haywire/ui/pan_zoom/minimap.py:164:100: E501 Line too long (110 > 99)
    |
162 |                     const minimapHeight = Math.max(2, viewHeight * scaleFactor);
163 |                     
164 |                     viewportRect = {{ x: minimapX, y: minimapY, width: minimapWidth, height: minimapHeight }};
    |                                                                                                    ^^^^^^^^^^^ E501
165 |                     drawMinimap();
166 |                 }}
    |

src/haywire/ui/pan_zoom/minimap.py:195:100: E501 Line too long (115 > 99)
    |
193 |                     for (let x = boundsX; x < boundsX + boundsWidth; x += gridSpacing) {{
194 |                         for (let y = boundsY; y < boundsY + boundsHeight; y += gridSpacing) {{
195 |                             if (x + gridSize <= boundsX + boundsWidth && y + gridSize <= boundsY + boundsHeight) {{
    |                                                                                                    ^^^^^^^^^^^^^^^^ E501
196 |                                 ctx.fillRect(x, y, gridSize, gridSize);
197 |                             }}
    |

src/haywire/ui/pan_zoom/minimap.py:208:100: E501 Line too long (116 > 99)
    |
206 |                     const clampedX = Math.max(0, Math.min(viewportRect.x, {self.minimap_width}));
207 |                     const clampedY = Math.max(0, Math.min(viewportRect.y, {self.minimap_height}));
208 |                     const clampedWidth = Math.max(1, Math.min(viewportRect.width, {self.minimap_width} - clampedX));
    |                                                                                                    ^^^^^^^^^^^^^^^^^ E501
209 |                     const clampedHeight = Math.max(1, Math.min(viewportRect.height, {self.minimap_height} - clampedY));
    |

src/haywire/ui/pan_zoom/minimap.py:209:100: E501 Line too long (119 > 99)
    |
207 |                     const clampedY = Math.max(0, Math.min(viewportRect.y, {self.minimap_height}));
208 |                     const clampedWidth = Math.max(1, Math.min(viewportRect.width, {self.minimap_width} - clampedX));
209 |                     const clampedHeight = Math.max(1, Math.min(viewportRect.height, {self.minimap_height} - clampedY));
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^ E501
210 |                     
211 |                     ctx.fillRect(clampedX, clampedY, clampedWidth, clampedHeight);
    |

src/haywire/ui/pan_zoom/minimap.py:216:100: E501 Line too long (101 > 99)
    |
215 |                 function minimapToContent(minimapX, minimapY) {{
216 |                     const contentX = contentBounds.minX + (minimapX - MINIMAP_PADDING) / scaleFactor;
    |                                                                                                    ^^ E501
217 |                     const contentY = contentBounds.minY + (minimapY - MINIMAP_PADDING) / scaleFactor;
218 |                     return {{ x: contentX, y: contentY }};
    |

src/haywire/ui/pan_zoom/minimap.py:217:100: E501 Line too long (101 > 99)
    |
215 |                 function minimapToContent(minimapX, minimapY) {{
216 |                     const contentX = contentBounds.minX + (minimapX - MINIMAP_PADDING) / scaleFactor;
217 |                     const contentY = contentBounds.minY + (minimapY - MINIMAP_PADDING) / scaleFactor;
    |                                                                                                    ^^ E501
218 |                     return {{ x: contentX, y: contentY }};
219 |                 }}
    |

src/haywire/ui/pan_zoom/minimap.py:228:100: E501 Line too long (104 > 99)
    |
226 |                     const contentPos = minimapToContent(minimapX, minimapY);
227 |                     
228 |                     const mainContainer = document.getElementById('{self.zoom_container.container_id}');
    |                                                                                                    ^^^^^ E501
229 |                     if (mainContainer && mainContainer._zoomPanControls) {{
230 |                         const containerRect = mainContainer.getBoundingClientRect();
    |

src/haywire/ui/pan_zoom/minimap.py:261:100: E501 Line too long (104 > 99)
    |
259 |                     const contentDeltaY = deltaY / scaleFactor;
260 |                     
261 |                     const mainContainer = document.getElementById('{self.zoom_container.container_id}');
    |                                                                                                    ^^^^^ E501
262 |                     if (mainContainer && mainContainer._zoomPanControls) {{
263 |                         const currentPan = mainContainer._zoomPanControls.getPan();
    |

src/haywire/ui/pan_zoom/minimap.py:306:100: E501 Line too long (117 > 99)
    |
304 |             if (content) {{
305 |                 // Scan content and update bounds
306 |                 const elements = content.querySelectorAll('.zoomable-card, .card, [class*="card"], [class*="item"]');
    |                                                                                                    ^^^^^^^^^^^^^^^^^^ E501
307 |                 
308 |                 let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    |

src/haywire/ui/pan_zoom/minimap.py:322:100: E501 Line too long (105 > 99)
    |
321 |                         if (transform) {{
322 |                             const translateMatch = transform.match(/translate\\(([^,]+),\\s*([^)]+)\\)/);
    |                                                                                                    ^^^^^^ E501
323 |                             const scaleMatch = transform.match(/scale\\(([^)]+)\\)/);
    |

src/haywire/ui/pan_zoom/minimap.py:395:100: E501 Line too long (105 > 99)
    |
393 |             const minimap = document.getElementById('{self.minimap_id}');
394 |             if (minimap) {{
395 |                 minimap.style.cssText += '{position_styles.get(position, position_styles["top-right"])}';
    |                                                                                                    ^^^^^^ E501
396 |             }}
397 |         ''')
    |

src/haywire/ui/pan_zoom/minimap.py:429:100: E501 Line too long (106 > 99)
    |
427 |             const mainContainer = document.getElementById('{self.zoom_container.container_id}');
428 |             
429 |             if (minimap && minimap._minimapControls && mainContainer && mainContainer._zoomPanControls) {{
    |                                                                                                    ^^^^^^^ E501
430 |                 const currentZoom = mainContainer._zoomPanControls.getZoom();
431 |                 const currentPan = mainContainer._zoomPanControls.getPan();
    |

src/haywire/ui/pan_zoom/zoom_pan_test.py:17:100: E501 Line too long (101 > 99)
   |
16 | def create_zoom_pan_info(container: ZoomPanContainer) -> ui.label:
17 |     """Create info display with comprehensive performance metrics for current zoom and pan values."""
   |                                                                                                    ^^ E501
18 |     info_label = ui.label().classes('zoom-pan-info')
   |

src/haywire/ui/pan_zoom/zoom_pan_test.py:115:100: E501 Line too long (110 > 99)
    |
113 |         with ui.row().classes('w-full gap-4').style('height: 80vh;'):
114 |             # Right side with zoom container (create first so we can reference it)
115 |             with ui.card().classes('flex-grow').style('height: 100%; display: flex; flex-direction: column;'):
    |                                                                                                    ^^^^^^^^^^^ E501
116 |                 ui.label('Zoomable Content Area').classes('text-lg mb-2 flex-shrink-0')
    |

src/haywire/ui/pan_zoom/zoom_pan_test.py:141:100: E501 Line too long (142 > 99)
    |
139 | …om-[2000px] relative')
140 | …
141 | …h-32 bg-blue-100 flex flex-col items-center justify-center zoom-pan-lod0 node-card'):
    |                                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
142 | …
143 | … be draggable, not pan the view)
    |

src/haywire/ui/pan_zoom/zoom_pan_test.py:144:100: E501 Line too long (100 > 99)
    |
142 | …                     with ui.column():
143 | …                         # Drag handle (should be draggable, not pan the view)
144 | …                         with ui.row().classes('drag-handle w-full justify-center mb-1'):
    |                                                                                          ^ E501
145 | …                             ui.icon('drag_indicator').classes('text-grey-6 text-xs')
146 | …                         ui.label(f'Item {i+1}').classes('text-center text-sm mb-2 zoom-pan-lod1')
    |

src/haywire/ui/pan_zoom/zoom_pan_test.py:146:100: E501 Line too long (109 > 99)
    |
144 | …     with ui.row().classes('drag-handle w-full justify-center mb-1'):
145 | …         ui.icon('drag_indicator').classes('text-grey-6 text-xs')
146 | …     ui.label(f'Item {i+1}').classes('text-center text-sm mb-2 zoom-pan-lod1')
    |                                                                      ^^^^^^^^^^ E501
147 | …     ui.input(value='some text').props('clearable outlined').classes('text-xs zoom-pan-lod2').style('cursor: text; pointer-events: a…
148 | …     # Add a port-like element
    |

src/haywire/ui/pan_zoom/zoom_pan_test.py:147:100: E501 Line too long (169 > 99)
    |
145 | …es('text-grey-6 text-xs')
146 | …xt-center text-sm mb-2 zoom-pan-lod1')
147 | …clearable outlined').classes('text-xs zoom-pan-lod2').style('cursor: text; pointer-events: auto;')
    |                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
148 | …
149 | …er mt-1'):
    |

src/haywire/ui/pan_zoom/zoom_pan_test.py:150:100: E501 Line too long (145 > 99)
    |
148 | …nt
149 | …justify-center mt-1'):
150 | …lasses('port output-port w-3 h-3 bg-red-500 rounded-full').style('cursor: crosshair;')
    |                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
151 | …
152 | …
    |

src/haywire/ui/pan_zoom/zoom_pan_test.py:165:100: E501 Line too long (119 > 99)
    |
164 |             # Left panel with controls and documentation (create after zoom_container)
165 |             with ui.card().classes('w-80 flex-shrink-0').style('height: 100%; display: flex; flex-direction: column;'):
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^ E501
166 |                 ui.label('Controls & Info').classes('text-xl font-bold mb-4')
    |

src/haywire/ui/pan_zoom/zoom_pan_test.py:171:100: E501 Line too long (108 > 99)
    |
169 |                 with ui.column().classes('gap-2 mb-6'):
170 |                     ui.label('Demo Controls').classes('text-lg font-semibold mb-2')
171 |                     ui.button('Zoom to 2x', on_click=lambda: zoom_container.set_zoom(2.0)).classes('w-full')
    |                                                                                                    ^^^^^^^^^ E501
172 |                     ui.button('Pan to (100, 50)', on_click=lambda: zoom_container.set_pan(100, 50)).classes('w-full')
173 |                     ui.button('Reset View', on_click=zoom_container.reset_view).classes('w-full')
    |

src/haywire/ui/pan_zoom/zoom_pan_test.py:172:100: E501 Line too long (117 > 99)
    |
170 |                     ui.label('Demo Controls').classes('text-lg font-semibold mb-2')
171 |                     ui.button('Zoom to 2x', on_click=lambda: zoom_container.set_zoom(2.0)).classes('w-full')
172 |                     ui.button('Pan to (100, 50)', on_click=lambda: zoom_container.set_pan(100, 50)).classes('w-full')
    |                                                                                                    ^^^^^^^^^^^^^^^^^^ E501
173 |                     ui.button('Reset View', on_click=zoom_container.reset_view).classes('w-full')
174 |                     ui.button('Fit Content', on_click=zoom_container.fit_to_content).classes('w-full')
    |

src/haywire/ui/pan_zoom/zoom_pan_test.py:174:100: E501 Line too long (102 > 99)
    |
172 |                     ui.button('Pan to (100, 50)', on_click=lambda: zoom_container.set_pan(100, 50)).classes('w-full')
173 |                     ui.button('Reset View', on_click=zoom_container.reset_view).classes('w-full')
174 |                     ui.button('Fit Content', on_click=zoom_container.fit_to_content).classes('w-full')
    |                                                                                                    ^^^ E501
175 |                     
176 |                     # Performance controls
    |

src/haywire/ui/pan_zoom/zoom_pan_test.py:181:100: E501 Line too long (101 > 99)
    |
179 |                     ui.button('Show Performance Summary', 
180 |                              on_click=lambda: ui.notify(zoom_container.get_performance_summary(), 
181 |                                                        type='info', timeout=10000)).classes('w-full')
    |                                                                                                    ^^ E501
182 |                     ui.button('Reset Performance Metrics', 
183 |                              on_click=lambda: (zoom_container.reset_performance_metrics(), 
    |

src/haywire/ui/pan_zoom/zoom_pan_test.py:184:100: E501 Line too long (120 > 99)
    |
182 |                     ui.button('Reset Performance Metrics', 
183 |                              on_click=lambda: (zoom_container.reset_performance_metrics(), 
184 |                                              ui.notify('Performance metrics reset', type='positive'))).classes('w-full')
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^ E501
185 |                 
186 |                 # Controls documentation
    |

src/haywire/ui/pan_zoom/zoom_pan_vue.py:223:100: E501 Line too long (112 > 99)
    |
221 |         self.run_method('$el._zoomPanControls.fitToContent')
222 |     
223 |     def set_zoom(self, zoom: float, center_x: Optional[float] = None, center_y: Optional[float] = None) -> None:
    |                                                                                                    ^^^^^^^^^^^^^ E501
224 |         """Set zoom level programmatically."""
225 |         if center_x is not None and center_y is not None:
    |

src/haywire/ui/pan_zoom/zoom_pan_vue.py:259:100: E501 Line too long (101 > 99)
    |
258 | def create_zoom_pan_info(container: ZoomPanContainer) -> ui.label:
259 |     """Create info display with comprehensive performance metrics for current zoom and pan values."""
    |                                                                                                    ^^ E501
260 |     info_label = ui.label().classes('zoom-pan-info')
    |

src/haywire/ui/pan_zoom/zoom_pan_vue.py:358:100: E501 Line too long (110 > 99)
    |
356 |         with ui.row().classes('w-full gap-4').style('height: 80vh;'):
357 |             # Right side with zoom container (create first so we can reference it)
358 |             with ui.card().classes('flex-grow').style('height: 100%; display: flex; flex-direction: column;'):
    |                                                                                                    ^^^^^^^^^^^ E501
359 |                 ui.label('Zoomable Content Area').classes('text-lg mb-2 flex-shrink-0')
    |

src/haywire/ui/pan_zoom/zoom_pan_vue.py:374:100: E501 Line too long (132 > 99)
    |
372 |                     with ui.grid(columns=50).classes('gap-6 p-8'):
373 |                         for i in range(500):
374 |                             with ui.card().classes('w-32 h-32 bg-blue-100 flex flex-col items-center justify-center zoomable-card'):
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
375 |                                 ui.label(f'Item {i+1}').classes('text-center text-sm mb-2')
376 |                                 ui.button('Click', on_click=lambda i=i: ui.notify(f'Clicked item {i+1}')).classes('text-xs')
    |

src/haywire/ui/pan_zoom/zoom_pan_vue.py:376:100: E501 Line too long (124 > 99)
    |
374 |                             with ui.card().classes('w-32 h-32 bg-blue-100 flex flex-col items-center justify-center zoomable-card'):
375 |                                 ui.label(f'Item {i+1}').classes('text-center text-sm mb-2')
376 |                                 ui.button('Click', on_click=lambda i=i: ui.notify(f'Clicked item {i+1}')).classes('text-xs')
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^ E501
377 |                 
378 |                 # Add controls
    |

src/haywire/ui/pan_zoom/zoom_pan_vue.py:383:100: E501 Line too long (119 > 99)
    |
382 |             # Left panel with controls and documentation
383 |             with ui.card().classes('w-80 flex-shrink-0').style('height: 100%; display: flex; flex-direction: column;'):
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^ E501
384 |                 ui.label('Controls & Info').classes('text-xl font-bold mb-4')
    |

src/haywire/ui/pan_zoom/zoom_pan_vue.py:389:100: E501 Line too long (108 > 99)
    |
387 |                 with ui.column().classes('gap-2 mb-6'):
388 |                     ui.label('Demo Controls').classes('text-lg font-semibold mb-2')
389 |                     ui.button('Zoom to 2x', on_click=lambda: zoom_container.set_zoom(2.0)).classes('w-full')
    |                                                                                                    ^^^^^^^^^ E501
390 |                     ui.button('Pan to (100, 50)', on_click=lambda: zoom_container.set_pan(100, 50)).classes('w-full')
391 |                     ui.button('Reset View', on_click=zoom_container.reset_view).classes('w-full')
    |

src/haywire/ui/pan_zoom/zoom_pan_vue.py:390:100: E501 Line too long (117 > 99)
    |
388 |                     ui.label('Demo Controls').classes('text-lg font-semibold mb-2')
389 |                     ui.button('Zoom to 2x', on_click=lambda: zoom_container.set_zoom(2.0)).classes('w-full')
390 |                     ui.button('Pan to (100, 50)', on_click=lambda: zoom_container.set_pan(100, 50)).classes('w-full')
    |                                                                                                    ^^^^^^^^^^^^^^^^^^ E501
391 |                     ui.button('Reset View', on_click=zoom_container.reset_view).classes('w-full')
392 |                     ui.button('Fit Content', on_click=zoom_container.fit_to_content).classes('w-full')
    |

src/haywire/ui/pan_zoom/zoom_pan_vue.py:392:100: E501 Line too long (102 > 99)
    |
390 |                     ui.button('Pan to (100, 50)', on_click=lambda: zoom_container.set_pan(100, 50)).classes('w-full')
391 |                     ui.button('Reset View', on_click=zoom_container.reset_view).classes('w-full')
392 |                     ui.button('Fit Content', on_click=zoom_container.fit_to_content).classes('w-full')
    |                                                                                                    ^^^ E501
393 |                     
394 |                     # Performance controls
    |

src/haywire/ui/pan_zoom/zoom_pan_vue.py:399:100: E501 Line too long (101 > 99)
    |
397 |                     ui.button('Show Performance Summary', 
398 |                              on_click=lambda: ui.notify(zoom_container.get_performance_summary(), 
399 |                                                        type='info', timeout=10000)).classes('w-full')
    |                                                                                                    ^^ E501
400 |                     ui.button('Reset Performance Metrics', 
401 |                              on_click=lambda: (zoom_container.reset_performance_metrics(), 
    |

src/haywire/ui/pan_zoom/zoom_pan_vue.py:402:100: E501 Line too long (120 > 99)
    |
400 |                     ui.button('Reset Performance Metrics', 
401 |                              on_click=lambda: (zoom_container.reset_performance_metrics(), 
402 |                                              ui.notify('Performance metrics reset', type='positive'))).classes('w-full')
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^ E501
403 |                 
404 |                 # Controls documentation
    |

src/haywire/ui/renderer/base.py:107:100: E501 Line too long (102 > 99)
    |
105 |             The rendered widget instance, or None if no widget was rendered
106 |         """
107 |         widget_instance, ui_element = self._widget_factory.render_widget(inlet.widget, inlet, node_id)
    |                                                                                                    ^^^ E501
108 |
109 |         if widget_instance:
    |

src/haywire/ui/renderer/decorator.py:61:100: E501 Line too long (109 > 99)
   |
59 |     def decorator(inner_cls: Type[T]) -> Type[T]:
60 |         if not issubclass(inner_cls, BaseRenderer):
61 |             raise TypeError(f"@renderer can only be applied to BaseNodeRenderer subclasses, got {inner_cls}")
   |                                                                                                    ^^^^^^^^^^ E501
62 |
63 |         # Set defaults from class name if not provided
   |

src/haywire/ui/renderer/factory.py:73:100: E501 Line too long (131 > 99)
   |
72 |     # this method is called by UINode to render the node
73 |     def render(self, renderer_registry_key: str | None, wrapper: NodeWrapper, _is_error_render: bool = False) -> UINodeCard | None:
   |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
74 |         """Render a node with the renderer with the renderer_registry_key.
   |

src/haywire/ui/renderer/factory.py:90:100: E501 Line too long (168 > 99)
   |
88 | …o default renderer available
89 | … no default renderer is set"
90 | … '{wrapper.node_id}' no render or default defined. Using '{NO_RENDERER_DEFINED}' as renderer key")
   |                               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
91 | …
92 | …
   |

src/haywire/ui/renderer/factory.py:97:100: E501 Line too long (103 > 99)
   |
96 |         try:
97 |             # if the node is undefined, we throw an error that should be caught with the error renderer
   |                                                                                                    ^^^^ E501
98 |             if renderer_registry_key is NO_RENDERER_DEFINED:
99 |                 raise HaywireException(
   |

src/haywire/ui/renderer/factory.py:102:100: E501 Line too long (127 > 99)
    |
100 |                     category="Renderer Lookup Error",
101 |                     operation="renderer_lookup",
102 |                     message="No renderer registry key provided and no default renderer has been set in the renderer registry.",
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
103 |                     suggestions=[
104 |                         "1. Provide a valid renderer registry key",
    |

src/haywire/ui/renderer/factory.py:115:100: E501 Line too long (145 > 99)
    |
113 | …rer_registry_key)
114 | …
115 | …y.label}' - '{wrapper.node_id}' attempting to render Using '{renderer_registry_key}'")
    |                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
116 | …=wrapper)
117 | …y.label}' - '{wrapper.node_id}' successfully rendered Using '{renderer_registry_key}'")
    |

src/haywire/ui/renderer/factory.py:117:100: E501 Line too long (146 > 99)
    |
115 | …y.label}' - '{wrapper.node_id}' attempting to render Using '{renderer_registry_key}'")
116 | …=wrapper)
117 | …y.label}' - '{wrapper.node_id}' successfully rendered Using '{renderer_registry_key}'")
    |                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
118 | …
119 | …ed, cache it
    |

src/haywire/ui/renderer/factory.py:123:100: E501 Line too long (167 > 99)
    |
122 | …
123 | …_key}' for node '{wrapper.node.identity.label}' with node id '{wrapper.node_id}'", exc_info=True)
    |                               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
124 | …
125 | …
    |

src/haywire/ui/renderer/factory.py:129:100: E501 Line too long (153 > 99)
    |
127 | …
128 | …
129 | …_registry_key}' for node '{wrapper.node.identity.label}' with node id '{wrapper.node_id}'"
    |                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
130 | …
131 | …_.class_library if renderer_instance else None,
    |

src/haywire/ui/renderer/factory.py:131:100: E501 Line too long (110 > 99)
    |
129 | …         message=f"Failed to use renderer '{renderer_registry_key}' for node '{wrapper.node.identity.label}' with node id '{wrapper.…
130 | …     ).enrich(
131 | …         library_identity=renderer_instance.__class__.class_library if renderer_instance else None,
    |                                                                                          ^^^^^^^^^^^ E501
132 | …         registry_key=renderer_registry_key
133 | …     )
    |

src/haywire/ui/renderer/factory.py:143:100: E501 Line too long (164 > 99)
    |
141 | …
142 | …
143 | …or '{error.message}' on '{wrapper.node.identity.label}' - '{wrapper.node_id}' without renderer")
    |                                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
144 | …
    |

src/haywire/ui/renderer/factory.py:148:100: E501 Line too long (150 > 99)
    |
146 | …
147 | …
148 | …rapper.node.identity.label}' - '{wrapper.node_id}' with '{error_renderer_registry_key}'")
    |                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
149 | …
150 | …
    |

src/haywire/ui/renderer/factory.py:156:100: E501 Line too long (151 > 99)
    |
154 | …
155 | …
156 | …rapper.node.identity.label}' - '{wrapper.node_id}' with '{error_renderer_registry_key}'")
    |                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
157 | …
158 | … error render that was executed 
    |

src/haywire/ui/renderer/factory.py:163:100: E501 Line too long (119 > 99)
    |
162 |         if ui_nodeCard:
163 |             logging.debug(f"About to return with ui_nodeCard on '{wrapper.node.identity.label}' - '{wrapper.node_id}'")
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^ E501
164 |             # Map renderer registry key to node ID for hot reload tracking
165 |             # this might not be the key of the renderer that actually gets used due to fallback
    |

src/haywire/ui/renderer/factory.py:174:100: E501 Line too long (103 > 99)
    |
172 |                 if wrapper.node_id in self._nodeid_to_renderer_regkey:
173 |                     previous_regkey = self._nodeid_to_renderer_regkey[wrapper.node_id]
174 |                     if wrapper.node_id in self._renderer_regkey_to_node_id.get(previous_regkey, set()):
    |                                                                                                    ^^^^ E501
175 |                         self._renderer_regkey_to_node_id[previous_regkey].remove(wrapper.node_id)
176 |                         logging.debug(f"  -> Cleanup render_key to node_id mapping: '{previous_regkey}' -> '{wrapper.node_id}'")
    |

src/haywire/ui/renderer/factory.py:176:100: E501 Line too long (128 > 99)
    |
174 |                     if wrapper.node_id in self._renderer_regkey_to_node_id.get(previous_regkey, set()):
175 |                         self._renderer_regkey_to_node_id[previous_regkey].remove(wrapper.node_id)
176 |                         logging.debug(f"  -> Cleanup render_key to node_id mapping: '{previous_regkey}' -> '{wrapper.node_id}'")
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
177 |             
178 |                 # one to many mapping
    |

src/haywire/ui/renderer/factory.py:179:100: E501 Line too long (110 > 99)
    |
178 |                 # one to many mapping
179 |                 self._renderer_regkey_to_node_id.setdefault(renderer_registry_key, set()).add(wrapper.node_id)
    |                                                                                                    ^^^^^^^^^^^ E501
180 |                 # one to one mapping
181 |                 self._nodeid_to_renderer_regkey[wrapper.node_id] = renderer_registry_key
    |

src/haywire/ui/renderer/factory.py:182:100: E501 Line too long (124 > 99)
    |
180 |                 # one to one mapping
181 |                 self._nodeid_to_renderer_regkey[wrapper.node_id] = renderer_registry_key
182 |                 logging.debug(f"  -> Setup render_key to node_id mapping: '{renderer_registry_key}' -> '{wrapper.node_id}'")
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^ E501
183 |
184 |         return ui_nodeCard
    |

src/haywire/ui/renderer/factory.py:223:100: E501 Line too long (101 > 99)
    |
221 |         return renderer_instance
222 |         
223 |     def add_factory_lifecycle_subscriber(self, node_id: str, callback: FactoryEventCallback) -> None:
    |                                                                                                    ^^ E501
224 |         """
225 |         Register a customer callback for factory event notifications.
    |

src/haywire/ui/renderer/factory.py:238:100: E501 Line too long (104 > 99)
    |
238 |     def remove_factory_lifecycle_subscriber(self, node_id: str, callback: FactoryEventCallback) -> None:
    |                                                                                                    ^^^^^ E501
239 |         """
240 |         Unregister a customer callback.
    |

src/haywire/ui/renderer/factory.py:288:100: E501 Line too long (100 > 99)
    |
286 |                     # (most likely the error renderer), they might be interested to 
287 |                     # now about that new renderer and should be informed
288 |                     node_ids = set(self._renderer_regkey_to_node_id.get(NO_RENDERER_DEFINED, set()))
    |                                                                                                    ^ E501
289 |                     for node_id in node_ids:
290 |                         self._notify_factory_subscribers(node_id)
    |

src/haywire/ui/renderer/registry.py:33:100: E501 Line too long (131 > 99)
   |
31 |             return False
32 |
33 |     def _register_class(self, renderer_cls: type[IBaseRenderer], library_identity: Optional[LibraryIdentity] = None) -> str | None:
   |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
34 |         """
35 |         Register a renderer class.
   |

src/haywire/ui/renderer/registry.py:52:100: E501 Line too long (117 > 99)
   |
50 |         if renderer_cls.class_identity._is_error:
51 |             if self._error_renderer is not None:
52 |                 if renderer_cls.class_identity._error_priority > self._error_renderer.class_identity._error_priority:
   |                                                                                                    ^^^^^^^^^^^^^^^^^^ E501
53 |                     logging.warning(
54 |                         f"Overriding already registered error renderer: '{self._error_renderer.class_identity.registry_key}'"
   |

src/haywire/ui/renderer/registry.py:54:100: E501 Line too long (125 > 99)
   |
52 | …     if renderer_cls.class_identity._error_priority > self._error_renderer.class_identity._error_priority:
53 | …         logging.warning(
54 | …             f"Overriding already registered error renderer: '{self._error_renderer.class_identity.registry_key}'"
   |                                                                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
55 | …             f" with : '{renderer_cls.class_identity.registry_key}'"
56 | …             f" due to higher _error_priority ({renderer_cls.class_identity._error_priority} > {self._error_renderer.class_identity._…
   |

src/haywire/ui/renderer/registry.py:56:100: E501 Line too long (161 > 99)
   |
54 | …erer: '{self._error_renderer.class_identity.registry_key}'"
55 | …gistry_key}'"
56 | …r_cls.class_identity._error_priority} > {self._error_renderer.class_identity._error_priority})"
   |                                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
57 | …
58 | …
   |

src/haywire/ui/renderer/registry.py:68:100: E501 Line too long (102 > 99)
   |
66 |                 if self._error_renderer_name:
67 |                     logging.warning(
68 |                         f"Overriding already registered error renderer: '{self._error_renderer_name}'"
   |                                                                                                    ^^^ E501
69 |                         f" with : '{registry_key}'"
70 |                         f" due to higher _error_priority ({new_error_priority} > {self._error_priority})"
   |

src/haywire/ui/renderer/registry.py:70:100: E501 Line too long (105 > 99)
   |
68 |                         f"Overriding already registered error renderer: '{self._error_renderer_name}'"
69 |                         f" with : '{registry_key}'"
70 |                         f" due to higher _error_priority ({new_error_priority} > {self._error_priority})"
   |                                                                                                    ^^^^^^ E501
71 |                     )
72 |                 self._error_renderer_name = registry_key
   |

src/haywire/ui/renderer/registry.py:82:100: E501 Line too long (106 > 99)
   |
80 |                 if self._default_renderer_name:
81 |                     logging.warning(
82 |                         f"Overriding already registered default renderer: '{self._default_renderer_name}'"
   |                                                                                                    ^^^^^^^ E501
83 |                         f" with : '{registry_key}'"
84 |                         f" due to higher _default_priority ({new_default_priority} > {self._default_priority})"
   |

src/haywire/ui/renderer/registry.py:84:100: E501 Line too long (111 > 99)
   |
82 |                         f"Overriding already registered default renderer: '{self._default_renderer_name}'"
83 |                         f" with : '{registry_key}'"
84 |                         f" due to higher _default_priority ({new_default_priority} > {self._default_priority})"
   |                                                                                                    ^^^^^^^^^^^^ E501
85 |                     )
86 |                 self._default_renderer_name = registry_key
   |

src/haywire/ui/renderer/registry.py:102:100: E501 Line too long (116 > 99)
    |
100 |         if removed_class == self._error_renderer:
101 |             self._error_renderer = None
102 |             logging.warning(f"Error renderer '{registry_key}' unregistered, no error renderer left in registry")    
    |                                                                                                    ^^^^^^^^^^^^^^^^^ E501
103 |         
104 |         return removed_class
    |

src/haywire/ui/themes/loader.py:166:100: E501 Line too long (102 > 99)
    |
165 |                     if parent_theme is None:
166 |                         print(f"Warning: Parent theme '{extends_name}' not found for theme at {path}")
    |                                                                                                    ^^^ E501
167 |             
168 |             # Create TOMLTheme with parent reference
    |

src/haywire/ui/themes/loader.py:205:100: E501 Line too long (100 > 99)
    |
203 |         if not has_color_section:
204 |             raise ThemeValidationError(
205 |                 f"Theme must have at least one color section: {', '.join(color_sections)}{path_str}"
    |                                                                                                    ^ E501
206 |             )
    |

src/haywire/ui/themes/loader.py:222:100: E501 Line too long (107 > 99)
    |
220 |         # Raise ThemeValidationError with specific error messages
221 |         if errors:
222 |             error_msg = f"Theme validation failed{path_str}:\n" + "\n".join(f"  - {err}" for err in errors)
    |                                                                                                    ^^^^^^^^ E501
223 |             raise ThemeValidationError(error_msg)
    |

src/haywire/ui/themes/loader.py:243:100: E501 Line too long (110 > 99)
    |
241 |             # Check if value is a string
242 |             if not isinstance(value, str):
243 |                 errors.append(f"[{section_name}] '{key}': value must be a string, got {type(value).__name__}")
    |                                                                                                    ^^^^^^^^^^^ E501
244 |                 continue
    |

src/haywire/ui/themes/loader.py:262:100: E501 Line too long (105 > 99)
    |
261 |     @classmethod
262 |     def reload_theme(cls, theme_name: str, theme_registry: Optional[Dict] = None) -> Optional[TOMLTheme]:
    |                                                                                                    ^^^^^^ E501
263 |         """
264 |         Force reload a theme from disk, bypassing cache.
    |

src/haywire/ui/themes/utils.py:65:100: E501 Line too long (112 > 99)
   |
63 |         # Handle short form (#RGB -> #RRGGBB)
64 |         if len(hex_color) == 4:  # #RGB
65 |             hex_color = f"#{hex_color[1]}{hex_color[1]}{hex_color[2]}{hex_color[2]}{hex_color[3]}{hex_color[3]}"
   |                                                                                                    ^^^^^^^^^^^^^ E501
66 |         
67 |         # Extract R, G, B values
   |

src/haywire/ui/themes/utils.py:178:100: E501 Line too long (107 > 99)
    |
176 |         # If #RGB format, expand to #RRGGBB
177 |         if cls.HEX_SHORT_PATTERN.match(hex_color):
178 |             return f"#{hex_color[1]}{hex_color[1]}{hex_color[2]}{hex_color[2]}{hex_color[3]}{hex_color[3]}"
    |                                                                                                    ^^^^^^^^ E501
179 |         
180 |         # Ensure uppercase
    |

src/haywire/ui/ui_node.py:68:100: E501 Line too long (116 > 99)
   |
67 |         # Subscribe to factory renderer changes for hot reload support
68 |         self.factory.add_factory_lifecycle_subscriber(self.wrapper.node_id, self._listen_on_factory_lifecycle_event)
   |                                                                                                    ^^^^^^^^^^^^^^^^^ E501
69 |
70 |         self.container.client.on_disconnect(lambda: self.cleanup())
   |

src/haywire/ui/ui_node.py:118:99: E501 Line too long (100 > 99)
    |
116 |             event: The hot reload event with complete context
117 |         """
118 |         logging.debug(f"🔄 UINode {self.wrapper.node_id}: Wrapper event - {event.event_type.value}")
    |                                                                                                    ^ E501
119 |
120 |         if event.event_type == LifeCycleEventType.CLASS_ADDED:
    |

src/haywire/ui/ui_node.py:133:100: E501 Line too long (115 > 99)
    |
131 | …     elif event.is_warning_event():
132 | …         # Error occurred during initialization or migration
133 | …         _error_renderer_reg_key: str | None = self.factory._renderer_registry.get_error_renderer_registry_key()
    |                                                                                                  ^^^^^^^^^^^^^^^^ E501
134 | …         logging.debug(f"⚠️ Node error: Re-rendering node {self.wrapper.node_id} with error renderer '{_error_renderer_reg_key}'")
135 | …         self.render(_error_renderer_reg_key, _is_error_render=True)
    |

src/haywire/ui/ui_node.py:134:101: E501 Line too long (132 > 99)
    |
132 | …r migration
133 | …lf.factory._renderer_registry.get_error_renderer_registry_key()
134 | …ing node {self.wrapper.node_id} with error renderer '{_error_renderer_reg_key}'")
    |                                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
135 | …_error_render=True)
    |

src/haywire/ui/ui_node.py:153:100: E501 Line too long (115 > 99)
    |
151 |             self.render()
152 |
153 |     def render(self, renderer_name: str | None = None, _is_error_render: bool = False) -> bool:                    
    |                                                                                                    ^^^^^^^^^^^^^^^^ E501
154 |         #IMPORTANT: This may be called from background threads (file watcher).
155 |         # We use ui.context.client to ensure UI updates run in the correct context.
    |

src/haywire/ui/ui_node.py:180:100: E501 Line too long (110 > 99)
    |
178 |                     self.container_slot.clear()  # NiceGUI handles cleanup reliably
179 |                 else:
180 |                     self.container_slot = ui.column().classes('ui-node-slot').props(f'id="{self.ui_node_id}"')
    |                                                                                                    ^^^^^^^^^^^ E501
181 |                 
182 |                 # Render into the container slot
    |

src/haywire/ui/ui_node.py:188:100: E501 Line too long (107 > 99)
    |
187 |                     if renderer_name is None:
188 |                         renderer_name = self.factory._renderer_registry.get_default_renderer_registry_key()
    |                                                                                                    ^^^^^^^^ E501
189 |
190 |                     self.current_ui_card = self.factory.render(renderer_name, self.wrapper, _is_error_render=_is_error_render)
    |

src/haywire/ui/ui_node.py:190:100: E501 Line too long (126 > 99)
    |
188 |                         renderer_name = self.factory._renderer_registry.get_default_renderer_registry_key()
189 |
190 |                     self.current_ui_card = self.factory.render(renderer_name, self.wrapper, _is_error_render=_is_error_render)
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
191 |
192 |                     self._emit_sync_event()
    |

src/haywire/ui/ui_node.py:273:100: E501 Line too long (119 > 99)
    |
271 |         """
272 |         logging.info(f"🔌 Cleaning up UINode {self.wrapper.node_id} ..")
273 |         self.factory.remove_factory_lifecycle_subscriber(self.wrapper.node_id, self._listen_on_factory_lifecycle_event)
    |                                                                                                    ^^^^^^^^^^^^^^^^^^^^ E501
    |

src/haywire/ui/utils.py:57:100: E501 Line too long (116 > 99)
   |
57 | def generate_connection_uuid(outlet_node_id: str, outlet_pin_id: str, inlet_node_id: str, inlet_pin_id: str) -> str:
   |                                                                                                    ^^^^^^^^^^^^^^^^^ E501
58 |     """
59 |     Generate a unique connection identifier for UI and graph systems.
   |

src/haywire/ui/utils.py:76:100: E501 Line too long (145 > 99)
   |
74 | …ode_456__input'
75 | …
76 | …et_node_id, outlet_pin_id)}__{generate_pin_uuid('inlet', inlet_node_id, inlet_pin_id)}"
   |                                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
   |

src/haywire/ui/utils.py:107:100: E501 Line too long (112 > 99)
    |
105 |     parts = connection_uuid.split('__')
106 |     if len(parts) != 7:
107 |         raise ValueError(f"Invalid connection ID format: {connection_uuid}. Expected 7 parts, got {len(parts)}")
    |                                                                                                    ^^^^^^^^^^^^^ E501
108 |
109 |     if parts[0] != 'connection':
    |

src/haywire/ui/widget/base.py:7:100: E501 Line too long (100 > 99)
  |
5 | from haywire.core.types.ports import DataPort
6 | from haywire.ui.widget.binding import PropertyBinding
7 | from haywire.ui.widget.converters import BindingConverter, BindingMode, PrimitiveUnwrappingConverter
  |                                                                                                    ^ E501
8 | from haywire.ui.widget.interface import IWidget
  |

src/haywire/ui/widget/base.py:37:100: E501 Line too long (111 > 99)
   |
35 |         self.element = element
36 |         self.element_id: str = element.id
37 |         self.ui_properties: Dict[str, Any] = element.ui.get('properties', {}) if hasattr(element, 'ui') else {}
   |                                                                                                    ^^^^^^^^^^^^ E501
38 |         
39 |         # UI element (created during render)
   |

src/haywire/ui/widget/base.py:186:100: E501 Line too long (106 > 99)
    |
184 |     def cleanup(self) -> None:
185 |         """Clean up bindings and resources"""
186 |         print(f"Cleaning up widget: {self.class_identity.registry_key} for element ID: {self.element_id}")
    |                                                                                                    ^^^^^^^ E501
187 |         
188 |         # Deactivate all bindings
    |

src/haywire/ui/widget/binding.py:18:100: E501 Line too long (115 > 99)
   |
16 | from haywire.core.types.ports import DataPort
17 | from haywire.core.data.fields import PrimitiveField, ComplexField, PooledField, ArrayField
18 | from haywire.ui.widget.converters import BindingConverter, BindingMode, PrimitiveUnwrappingConverter, UpdateTrigger
   |                                                                                                    ^^^^^^^^^^^^^^^^ E501
   |

src/haywire/ui/widget/decorator.py:60:100: E501 Line too long (101 > 99)
   |
58 |     def decorator(inner_cls: Type[T]) -> Type[T]:
59 |         if not issubclass(inner_cls, IWidget):
60 |             raise TypeError(f"@widget can only be applied to BaseWidget subclasses, got {inner_cls}")
   |                                                                                                    ^^ E501
61 |
62 |         if 'compatible_types' not in kwargs:
   |

src/haywire/ui/widget/decorator.py:70:100: E501 Line too long (102 > 99)
   |
68 |         types = kwargs['compatible_types']
69 |
70 |         # However, we allow no type constraints. This has to be explicit by setting an empty set/list.
   |                                                                                                    ^^^ E501
71 |
72 |         for typ in types:
   |

src/haywire/ui/widget/factory.py:50:100: E501 Line too long (115 > 99)
   |
48 |             self._widget_lifecycle_subscribers.discard(callback)
49 |
50 |     def render_widget(self, registry_key: str, inlet: DataPort, node_id: str) -> tuple[IWidget | None, ui.element]:
   |                                                                                                    ^^^^^^^^^^^^^^^^ E501
51 |         """Render a widget for the given inlet and return the widget instance.
   |

src/haywire/ui/widget/factory.py:80:100: E501 Line too long (138 > 99)
   |
78 | …y if lc_event is not None else None
79 | …ent is not None else None
80 | …inlet.widget}' for inlet '{inlet.id}' in node '{node_id}': {error}", exc_info=True)
   |                                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E501
81 | …
82 | …(
   |

src/haywire/ui/widget/factory.py:86:100: E501 Line too long (114 > 99)
   |
84 |                     category="Widget Render Error",
85 |                     operation="widget_lookup",
86 |                     message=f"Failed to render widget '{inlet.widget}' for inlet '{inlet.id}' in node '{node_id}'"
   |                                                                                                    ^^^^^^^^^^^^^^^ E501
87 |                 ).enrich(
88 |                     registry_key=inlet.widget,
   |

src/haywire/ui/widget/factory.py:105:100: E501 Line too long (111 > 99)
    |
103 |         return widget_instance, ui_element
104 |
105 |     def get_widget(self, registry_key: str, element: DataPort) -> tuple[IWidget | None, LifeCycleEvent | None]:
    |                                                                                                    ^^^^^^^^^^^^ E501
106 |         """
107 |         Get a widget instance for the given element using the widget registry.
    |

src/haywire/ui/widget/factory_interface.py:16:100: E501 Line too long (101 > 99)
   |
15 |     @abstractmethod
16 |     def render_widget(self, inlet: PortInlet, node_id: str) -> tuple[BaseWidget | None, ui.element] :
   |                                                                                                    ^^ E501
17 |         """Render a widget for the given inlet and return the widget instance.
   |

src/haywire/ui/widget/globals.py:74:100: E501 Line too long (104 > 99)
   |
72 |     if widget_class is None:
73 |         return True, None
74 |     # If widget class not found, skip validation. This will be caught later during widget instantiation.
   |                                                                                                    ^^^^^ E501
75 |     #    return False, f"Widget '{widget_registry_key}' not found in global registry"
   |

src/haywire/ui/widget/registry.py:26:100: E501 Line too long (106 > 99)
   |
24 |             return False
25 |
26 |     def _register_class(self, widget_cls: type[IWidget], library_identity: LibraryIdentity) -> str | None:
   |                                                                                                    ^^^^^^^ E501
27 |         """Register a UI widget with its metadata
   |

src/haywire/ui/widget/simple.py:59:100: E501 Line too long (101 > 99)
   |
57 |         self.element = element
58 |         self.element_id: str = element.id
59 |         self.ui_properties: dict = element.ui.get('properties', {}) if hasattr(element, 'ui') else {}
   |                                                                                                    ^^ E501
60 |         
61 |         # UI element (created during render)
   |

tests/libraries/haybale-TEST_A/haybale_test_a/types/data.py:87:100: E501 Line too long (106 > 99)
   |
85 |     def __str__(self) -> str:
86 |         """String representation of the test data."""
87 |         return f"TestData('{self.label}', value={self.value}, metadata_keys={list(self.metadata.keys())})"
   |                                                                                                    ^^^^^^^ E501
   |

tests/libraries/haybale-TEST_B/haybale_test_b/nodes/processor.py:97:100: E501 Line too long (106 > 99)
   |
95 |             # Process existing TestData
96 |             test_data_out = TestData(
97 |                 value=test_data_in.value if test_data_in.value is None else test_data_in.value + modifier,
   |                                                                                                    ^^^^^^^ E501
98 |                 label=f"Processed: {test_data_in.label}",
99 |                 metadata={**test_data_in.metadata, "processed_by": "test_b.test_processor"}
   |

Found 295 errors.
(haywire) mfroehli@NX-41545 haywire-repo % 