# Fragmenting

Isolated form updates from individual nodes to handle local validation and avoid expensive `read_form_to_state` calls on every form input change.

## Fragments per page

- src/pages/contingent_markers.py:
  - `global_order` wrap text input with fragment, no input validation needed
  - feature multiselect: no change, should re-render on form change
  - `global_markers`: wrap markerlist with fragment, validation handled by existing helper
  - `_render_entry`: wrap with fragment, validation handled by markerlist helper
- src/pages/feature_combinations.py:
