"""
Grid Layout Engine for Prism Desktop
Handles the mathematical logic for placing buttons in the dashboard grid.
"""

class GridLayoutEngine:
    """
    Calculates grid positions for buttons based on their configuration and spans.
    Decouples layout logic from the UI rendering in Dashboard.
    """
    
    def __init__(self, cols: int = 4):
        self.cols = cols

    def calculate_layout(self, buttons: list, rows: int) -> list[tuple]:
        """
        Calculate positions for all buttons.
        
        Args:
            buttons: List of DashboardButton objects (or objects with .config, .slot, .span_x/y attrs)
            rows: Total number of rows in the grid
            
        Returns:
            List of tuples: (button, row, col, span_y, span_x)
            Buttons that shouldn't be shown are not included in the list.
        """
        occupied = set()
        placements = []
        
        # Separate configured buttons from empty Add buttons
        configured_buttons = []
        empty_buttons = []
        
        for button in buttons:
            if button.config and button.config.get('entity_id'):
                configured_buttons.append(button)
            else:
                empty_buttons.append(button)
        
        # Sort configured buttons by config's slot (determines placement priority)
        # Use a stable sort key
        configured_buttons.sort(key=lambda b: b.config.get('slot', 999))
        
        # Pass 1: Place configured buttons
        for button in configured_buttons:
            # Get dimensions
            span_x = getattr(button, 'span_x', 1)
            span_y = getattr(button, 'span_y', 1)
            
            # Get preferred slot
            config_slot = button.config.get('slot', button.slot)
            
            # Preferred position
            pref_row = config_slot // self.cols
            pref_col = config_slot % self.cols
            
            # Check if preferred position works
            if self._can_place(pref_row, pref_col, span_x, span_y, rows, occupied):
                r, c = pref_row, pref_col
            else:
                # Fallback: find any available spot
                r, c = self._find_first_available(span_x, span_y, rows, occupied)
                
                # If no spot found (e.g. item too big for remaining space)
                if r is None:
                    continue 

            # Place user
            self._mark_occupied(r, c, span_x, span_y, occupied)
            placements.append((button, r, c, span_y, span_x))
            
            # Update the button's internal slot to match reality (for future saves)
            # Note: We return this info, but modifying the button object here is convenient 
            # if we assume 'buttons' are mutable objects. 
            # Ideally the caller handles state updates, but 'slot' is a property of the button.
            new_slot = r * self.cols + c
            # We don't modify button.config here to avoid side effects during calculation,
            # but we return the new slot implicitly via (row, col).
            
        # Pass 2: Fill empty holes with "Add" buttons
        # We need to fill specifically the empty cells that are NOT occupied
        
        # We iterate through all cells in order
        empty_idx = 0
        total_cells = rows * self.cols
        
        for i in range(total_cells):
            r = i // self.cols
            c = i % self.cols
            
            if (r, c) not in occupied:
                if empty_idx < len(empty_buttons):
                    btn = empty_buttons[empty_idx]
                    empty_idx += 1
                    
                    # Add buttons are always 1x1
                    placements.append((btn, r, c, 1, 1))
                    occupied.add((r, c))
                    
        return placements

    def find_first_empty_slot(self, buttons: list, rows: int, span_x: int = 1, span_y: int = 1) -> int:
        """Find the first visual slot index that is completely empty and fits the span."""
        occupied = set()
        
        # Calculate currently occupied cells from existing placed buttons
        for button in buttons:
            if not button.config: continue 
            if not button.isVisible(): continue # Only count visible buttons!
            
            # We assume button.slot is accurate to its current visual position
            sl = button.slot
            r = sl // self.cols
            c = sl % self.cols
            sx = getattr(button, 'span_x', 1)
            sy = getattr(button, 'span_y', 1)
            
            self._mark_occupied(r, c, sx, sy, occupied)

        # Check all possible slots
        return self._find_first_available_slot_index(span_x, span_y, rows, occupied)

    # --- Helper Methods ---

    def _can_place(self, r, c, span_x, span_y, max_rows, occupied):
        """Check if a rect fits at (r,c)."""
        if c + span_x > self.cols: return False
        if r + span_y > max_rows: return False
        
        for dy in range(span_y):
            for dx in range(span_x):
                if (r + dy, c + dx) in occupied:
                    return False
        return True

    def _mark_occupied(self, r, c, span_x, span_y, occupied):
        """Mark cells as occupied."""
        for dy in range(span_y):
            for dx in range(span_x):
                occupied.add((r + dy, c + dx))

    def _find_first_available(self, span_x, span_y, max_rows, occupied):
        """Finds first (r, c) that fits, or (None, None)."""
        # Search row by row, col by col
        for r in range(max_rows):
            for c in range(self.cols):
                if self._can_place(r, c, span_x, span_y, max_rows, occupied):
                    return r, c
        return None, None

    def _find_first_available_slot_index(self, span_x, span_y, max_rows, occupied):
        """Same as above but returns slot index."""
        r, c = self._find_first_available(span_x, span_y, max_rows, occupied)
        if r is not None:
            return r * self.cols + c
        return -1
