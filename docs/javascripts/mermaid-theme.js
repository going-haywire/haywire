// Material for MkDocs renders each Mermaid diagram in a closed shadow root and colours it
// with its own CSS, written for older Mermaid: it misses the arrowhead markers (their ids
// now carry the diagram's id), the titles of `else` sections and the flowchart markers, which
// then keep Mermaid's dark defaults and vanish in dark mode. This adds those rules to the
// CSS Material passes to Mermaid. Material uses the `mermaid` loaded before it, pinned in
// mkdocs.yml.
(function () {
  const extra = `
    marker[id$="-arrowhead"] path { fill: var(--md-mermaid-sequence-message-line-color); stroke: none; }
    .sectionTitle, .sectionTitle > tspan { fill: var(--md-mermaid-sequence-loop-fg-color); }
    .marker, .marker path, .marker .arrowMarkerPath {
      fill: var(--md-mermaid-edge-color) !important; stroke: var(--md-mermaid-edge-color) !important;
    }
  `;
  const initialize = mermaid.initialize.bind(mermaid);
  mermaid.initialize = (config) =>
    initialize({ ...config, themeCSS: (config.themeCSS || "") + extra });
})();
